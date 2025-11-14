# Análise: Implementação de Streaming para Geração de Contestação

## 📋 Visão Geral

Este documento detalha as mudanças necessárias para implementar **streaming visível** na geração de contestações, permitindo que o usuário veja o texto sendo gerado em tempo real, ao invés de esperar pela resposta completa.

---

## 🔍 Estado Atual

### Backend (`modules/llm_generator.py`)

**Localização**: Linhas 138-147

```python
response = self.client.messages.create(
    model=Config.CLAUDE_MODEL,
    max_tokens=max_tokens,
    temperature=temperatura,
    top_k=top_k,
    system=SYSTEM_PROMPT,
    messages=[
        {"role": "user", "content": prompt_usuario}
    ]
)
```

**Problema**:
- Usa `messages.create()` que é **síncrono/bloqueante**
- Aguarda a resposta completa antes de retornar
- Usuário fica esperando sem feedback visual durante a geração

### Frontend (`app.py`)

**Localização**: Linhas 307-313

```python
st.text_area(
    "Texto da contestação",
    value=res['contestacao'],
    height=500,
    label_visibility="collapsed"
)
```

**Problema**:
- Exibe apenas o resultado final
- Sem atualização em tempo real
- Sem feedback de progresso

---

## ✅ Mudanças Necessárias

### 1️⃣ Backend: Implementar Streaming na API

#### Arquivo: `modules/llm_generator.py`

**Modificar o método `gerar_contestacao()` para suportar streaming:**

```python
def gerar_contestacao(
    self,
    dados_peticao: Dict,
    contexto_rag: Dict,
    temperatura: float = Config.DEFAULT_TEMPERATURE,
    top_k: int = Config.DEFAULT_TOP_K,
    max_tokens: int = Config.DEFAULT_MAX_TOKENS,
    stream: bool = True  # NOVO PARÂMETRO
) -> Dict:
    """
    Gera contestação via Claude API com suporte a streaming

    Args:
        dados_peticao: Dados estruturados da petição
        contexto_rag: Contexto RAG construído
        temperatura: Parâmetro de temperatura (0.3-0.9)
        top_k: Parâmetro top-k (20-60)
        max_tokens: Tokens máximos para geração
        stream: Se True, retorna generator; se False, retorna texto completo

    Returns:
        Se stream=False: Dict com contestação gerada e metadados
        Se stream=True: Generator que yielda chunks de texto
    """
    # ... código de validação e preparação ...

    # Construir prompts
    prompt_usuario = construir_prompt_usuario(dados_peticao, contexto_rag)

    if stream:
        # NOVO: Modo streaming
        return self._gerar_com_streaming(
            prompt_usuario=prompt_usuario,
            temperatura=temperatura,
            top_k=top_k,
            max_tokens=max_tokens,
            dados_peticao=dados_peticao
        )
    else:
        # Modo original (não-streaming)
        # ... código atual ...
```

#### Adicionar novo método `_gerar_com_streaming()`:

```python
def _gerar_com_streaming(
    self,
    prompt_usuario: str,
    temperatura: float,
    top_k: int,
    max_tokens: int,
    dados_peticao: Dict
):
    """
    Generator que yielda chunks de texto em streaming

    Yields:
        Dict contendo:
        - 'chunk': Texto do chunk atual
        - 'done': Boolean indicando se terminou
        - 'metadata': Metadados (apenas no último chunk)
    """
    try:
        # Usar stream context manager
        with self.client.messages.stream(
            model=Config.CLAUDE_MODEL,
            max_tokens=max_tokens,
            temperature=temperatura,
            top_k=top_k,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": prompt_usuario}
            ]
        ) as stream:
            # Iterar sobre os eventos de streaming
            for text in stream.text_stream:
                yield {
                    'chunk': text,
                    'done': False,
                    'metadata': None
                }

            # Último chunk com metadados
            final_message = stream.get_final_message()

            metadados = {
                'model': Config.CLAUDE_MODEL,
                'temperatura': temperatura,
                'top_k': top_k,
                'input_tokens': final_message.usage.input_tokens,
                'output_tokens': final_message.usage.output_tokens,
                'stop_reason': final_message.stop_reason,
                'tipo_caso': dados_peticao.get('tipo_caso'),
                'confianca_classificacao': dados_peticao.get('confianca')
            }

            # Calcular custo
            custo_input = (metadados['input_tokens'] / 1_000_000) * 15
            custo_output = (metadados['output_tokens'] / 1_000_000) * 75
            custo_total = custo_input + custo_output

            yield {
                'chunk': '',
                'done': True,
                'metadata': {
                    **metadados,
                    'custo_estimado': custo_total
                }
            }

    except anthropic.APIError as e:
        yield {
            'chunk': '',
            'done': True,
            'error': str(e),
            'metadata': None
        }
    except Exception as e:
        yield {
            'chunk': '',
            'done': True,
            'error': str(e),
            'metadata': None
        }
```

---

### 2️⃣ Frontend: Atualizar UI para Mostrar Streaming

#### Arquivo: `app.py`

**Modificar a seção de geração (linhas ~210-240):**

```python
# Dentro do if uploaded_file:
if st.button("🚀 Gerar Contestação", type="primary", use_container_width=True):

    with st.spinner("Processando petição inicial..."):
        try:
            # 1. Processar documento
            dados_peticao = st.session_state.processor.processar_documento(
                uploaded_file
            )
            st.session_state.dados_peticao = dados_peticao

            # 2. Buscar contexto RAG
            resultado_rag = st.session_state.rag.buscar_contexto(
                dados_peticao['fatos_completos']
            )

            # 3. Construir contexto otimizado
            contexto_rag = st.session_state.context_builder.construir_contexto(
                dados_peticao,
                resultado_rag
            )

            st.success("✅ Processamento concluído!")

        except Exception as e:
            st.error(f"❌ Erro no processamento: {str(e)}")
            st.stop()

    # 4. NOVO: Gerar contestação com streaming
    st.divider()
    st.header("📄 Contestação em Geração...")

    # Container para o texto streaming
    contestacao_container = st.empty()
    metrics_container = st.empty()

    texto_acumulado = ""
    metadados_finais = None

    try:
        # Obter generator de streaming
        stream_generator = st.session_state.llm_generator.gerar_contestacao(
            dados_peticao=dados_peticao,
            contexto_rag=contexto_rag,
            temperatura=temperatura,
            top_k=top_k,
            max_tokens=max_tokens,
            stream=True  # ATIVAR STREAMING
        )

        # Processar chunks em tempo real
        for chunk_data in stream_generator:
            if chunk_data.get('error'):
                st.error(f"❌ Erro na geração: {chunk_data['error']}")
                break

            if not chunk_data['done']:
                # Acumular texto
                texto_acumulado += chunk_data['chunk']

                # Atualizar display em tempo real
                with contestacao_container.container():
                    st.text_area(
                        "Contestação sendo gerada...",
                        value=texto_acumulado,
                        height=500,
                        label_visibility="collapsed",
                        key=f"streaming_{len(texto_acumulado)}"
                    )
            else:
                # Último chunk - salvar metadados
                metadados_finais = chunk_data.get('metadata')

        # 5. Validar qualidade
        st.info("🔍 Validando qualidade...")
        validacao = st.session_state.validator.validar_contestacao(
            texto_acumulado,
            dados_peticao
        )

        # Salvar resultado completo
        st.session_state.resultado = {
            'contestacao': texto_acumulado,
            'dados_peticao': dados_peticao,
            'contexto_rag': contexto_rag,
            'metadados': metadados_finais,
            'validacao': validacao,
            'custo': metadados_finais['custo_estimado']
        }

        # Mostrar métricas finais
        with metrics_container.container():
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Tipo de Caso", dados_peticao.get('tipo_caso', 'N/A'))

            with col2:
                conf = dados_peticao.get('confianca', 0)
                st.metric("Confiança", f"{conf:.1%}")

            with col3:
                st.metric("Tokens", f"{metadados_finais['output_tokens']:,}")

            with col4:
                st.metric("Custo", f"${metadados_finais['custo_estimado']:.4f}")

        st.success("✅ Contestação gerada com sucesso!")

    except Exception as e:
        st.error(f"❌ Erro: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
```

---

## 🎯 Alternativa: Usar `st.write_stream()`

Streamlit tem uma função nativa `st.write_stream()` otimizada para streaming:

```python
# Versão simplificada usando st.write_stream()
contestacao_placeholder = st.empty()

def text_generator():
    """Adapter para st.write_stream()"""
    for chunk_data in stream_generator:
        if not chunk_data['done'] and not chunk_data.get('error'):
            yield chunk_data['chunk']

# Exibir streaming
with contestacao_placeholder.container():
    st.subheader("📜 Contestação")
    texto_acumulado = st.write_stream(text_generator())
```

---

## 📦 Dependências

### Verificar versão do pacote Anthropic

O streaming está disponível a partir da versão `0.18.0`. Verifique `requirements.txt`:

```txt
anthropic>=0.25.0  # ✅ Já suporta streaming
```

**Nenhuma mudança necessária** - a versão atual já suporta streaming.

---

## 🔧 Configurações Adicionais

### Opção: Adicionar toggle de streaming no sidebar

```python
# No sidebar de parâmetros
usar_streaming = st.sidebar.checkbox(
    "🔄 Streaming em Tempo Real",
    value=True,
    help="Mostra texto sendo gerado em tempo real"
)
```

---

## 📊 Comparação: Antes vs Depois

### Antes (Sem Streaming)

```
[Usuário clica "Gerar"]
  ↓
[Spinner girando... 30-60 segundos]
  ↓
[Texto completo aparece de uma vez]
```

**Experiência**:
- ❌ Sem feedback durante geração
- ❌ Parece travado
- ❌ Usuário não sabe o que está acontecendo

### Depois (Com Streaming)

```
[Usuário clica "Gerar"]
  ↓
[Texto começa a aparecer palavra por palavra]
  ↓
[Usuário vê a contestação sendo escrita em tempo real]
  ↓
[Métricas aparecem ao final]
```

**Experiência**:
- ✅ Feedback imediato
- ✅ Engajamento visual
- ✅ Transparência do processo

---

## 🚀 Implementação Recomendada - Passo a Passo

### Etapa 1: Backend (30 min)
1. Adicionar parâmetro `stream=True` ao método `gerar_contestacao()`
2. Implementar método `_gerar_com_streaming()`
3. Testar com script simples para verificar chunks

### Etapa 2: Frontend (45 min)
1. Modificar lógica do botão "Gerar Contestação"
2. Adicionar containers para texto streaming
3. Implementar loop de acumulação de chunks
4. Atualizar UI em tempo real

### Etapa 3: Testes (20 min)
1. Testar com petição real
2. Verificar se métricas aparecem corretamente
3. Validar tratamento de erros

### Etapa 4: Refinamentos (15 min)
1. Adicionar animações/indicadores
2. Ajustar altura/layout dos containers
3. Adicionar toggle opcional no sidebar

**Tempo total estimado**: ~2 horas

---

## ⚠️ Considerações Importantes

### 1. Performance de Rede
- Streaming funciona melhor com conexões estáveis
- Em redes lentas, pode haver delay entre chunks

### 2. Limitações do Streamlit
- `st.text_area()` com `key` dinâmica pode causar re-renderização
- Considere usar `st.markdown()` ou `st.write()` ao invés de `text_area()`

### 3. Estado da Aplicação
- Durante streaming, evitar que usuário clique novamente em "Gerar"
- Desabilitar botão ou usar `st.session_state` para controlar

### 4. Exemplo de Proteção Contra Duplo Clique

```python
# Adicionar flag de geração em andamento
if 'gerando' not in st.session_state:
    st.session_state.gerando = False

# No botão
if st.button(
    "🚀 Gerar Contestação",
    disabled=st.session_state.gerando,
    type="primary"
):
    st.session_state.gerando = True
    try:
        # ... lógica de geração ...
    finally:
        st.session_state.gerando = False
```

---

## 📝 Resumo das Mudanças

### Arquivos a Modificar

| Arquivo | Mudanças | Complexidade |
|---------|----------|--------------|
| `modules/llm_generator.py` | Adicionar método streaming + parâmetro stream | Média |
| `app.py` | Modificar lógica de geração e display | Média |
| `config/settings.py` | (Opcional) Adicionar flag `ENABLE_STREAMING` | Baixa |

### Linhas de Código

- **Backend**: ~60 linhas novas
- **Frontend**: ~40 linhas modificadas
- **Total**: ~100 linhas

---

## 🎬 Próximos Passos

1. ✅ Revisar esta análise
2. ⬜ Implementar backend streaming
3. ⬜ Implementar frontend streaming
4. ⬜ Testar end-to-end
5. ⬜ Commit e push das mudanças

---

## 📚 Referências

- [Anthropic Streaming Documentation](https://docs.anthropic.com/en/api/messages-streaming)
- [Streamlit Streaming Documentation](https://docs.streamlit.io/develop/api-reference/write-magic/st.write_stream)
- Código atual: `modules/llm_generator.py:138-147`
- Código atual: `app.py:245-313`

---

**Gerado em**: 2025-11-14
**Versão**: 1.0

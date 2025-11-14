# 🚀 Guia de Implementação: Streaming para Geração de Contestação

## ✅ Checklist de Implementação

### Fase 1: Preparação (5 min)

- [ ] Fazer backup dos arquivos atuais
- [ ] Ler documentação de referência:
  - `ANALISE_STREAMING.md` - Análise completa
  - `EXEMPLO_llm_generator_streaming.py` - Código backend
  - `EXEMPLO_app_streaming.py` - Código frontend
- [ ] Criar branch para desenvolvimento
- [ ] Verificar versão do pacote `anthropic` (>= 0.25.0)

### Fase 2: Backend (30-45 min)

- [ ] Abrir `modules/llm_generator.py`
- [ ] Adicionar parâmetro `stream: bool = False` ao método `gerar_contestacao()`
- [ ] Renomear método atual para `_gerar_sem_streaming()`
- [ ] Adicionar novo método `_gerar_com_streaming()`
- [ ] Adicionar lógica de escolha entre streaming/não-streaming
- [ ] Testar backend isoladamente

### Fase 3: Frontend (30-45 min)

- [ ] Abrir `app.py`
- [ ] Localizar seção de geração (linhas ~210-240)
- [ ] Adicionar containers para streaming (`st.empty()`)
- [ ] Modificar chamada para incluir `stream=True`
- [ ] Implementar loop de processamento de chunks
- [ ] Adicionar atualização em tempo real do texto
- [ ] Testar frontend com backend

### Fase 4: Testes (20 min)

- [ ] Testar com petição simples
- [ ] Testar com petição complexa
- [ ] Verificar tratamento de erros
- [ ] Validar métricas finais
- [ ] Testar regeneração

### Fase 5: Refinamentos (15 min)

- [ ] Ajustar estilos CSS
- [ ] Adicionar cursor piscando
- [ ] Melhorar mensagens de status
- [ ] Adicionar toggle streaming no sidebar (opcional)
- [ ] Documentar mudanças

### Fase 6: Finalização (10 min)

- [ ] Commit das mudanças
- [ ] Push para repositório
- [ ] Atualizar documentação do projeto

---

## 📝 Passo a Passo Detalhado

### PASSO 1: Backup

```bash
# Fazer backup dos arquivos que serão modificados
cp modules/llm_generator.py modules/llm_generator.py.backup
cp app.py app.py.backup
```

### PASSO 2: Modificar Backend

#### 2.1: Abrir arquivo

```bash
# Abrir no editor de preferência
code modules/llm_generator.py
```

#### 2.2: Modificar assinatura do método `gerar_contestacao()`

**Linha ~93** - Adicionar parâmetro `stream`:

```python
def gerar_contestacao(
    self,
    dados_peticao: Dict,
    contexto_rag: Dict,
    temperatura: float = Config.DEFAULT_TEMPERATURE,
    top_k: int = Config.DEFAULT_TOP_K,
    max_tokens: int = Config.DEFAULT_MAX_TOKENS,
    stream: bool = False  # 🔥 NOVO PARÂMETRO
) -> Union[Dict, Generator]:  # 🔥 MODIFICAR TIPO DE RETORNO
```

#### 2.3: Adicionar import

**Linha ~9** - Adicionar tipo Generator:

```python
from typing import Dict, List, Optional, Generator, Union
```

#### 2.4: Modificar corpo do método

**Linhas ~135-200** - Substituir por:

```python
# Construir prompts
prompt_usuario = construir_prompt_usuario(dados_peticao, contexto_rag)

# NOVA LÓGICA: Escolher entre streaming ou não
if stream:
    return self._gerar_com_streaming(
        prompt_usuario=prompt_usuario,
        temperatura=temperatura,
        top_k=top_k,
        max_tokens=max_tokens,
        dados_peticao=dados_peticao
    )
else:
    return self._gerar_sem_streaming(
        prompt_usuario=prompt_usuario,
        temperatura=temperatura,
        top_k=top_k,
        max_tokens=max_tokens,
        dados_peticao=dados_peticao
    )
```

#### 2.5: Renomear método original

Copiar código atual das linhas **135-200** para novo método `_gerar_sem_streaming()`:

```python
def _gerar_sem_streaming(
    self,
    prompt_usuario: str,
    temperatura: float,
    top_k: int,
    max_tokens: int,
    dados_peticao: Dict
) -> Dict:
    """Gera contestação de forma tradicional (sem streaming)"""

    # ... código original aqui ...
    response = self.client.messages.create(...)
    # ... resto do código ...
```

#### 2.6: Adicionar método de streaming

**Após `_gerar_sem_streaming()`**, adicionar:

```python
def _gerar_com_streaming(
    self,
    prompt_usuario: str,
    temperatura: float,
    top_k: int,
    max_tokens: int,
    dados_peticao: Dict
) -> Generator[Dict, None, None]:
    """Gera contestação com streaming"""

    try:
        with self.client.messages.stream(
            model=Config.CLAUDE_MODEL,
            max_tokens=max_tokens,
            temperature=temperatura,
            top_k=top_k,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt_usuario}]
        ) as stream:

            # Yield chunks de texto
            for text in stream.text_stream:
                yield {
                    'chunk': text,
                    'done': False,
                    'metadata': None,
                    'error': None
                }

            # Metadados finais
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
            metadados['custo_estimado'] = custo_input + custo_output

            # Último yield com metadados
            yield {
                'chunk': '',
                'done': True,
                'metadata': metadados,
                'error': None
            }

    except Exception as e:
        yield {
            'chunk': '',
            'done': True,
            'metadata': None,
            'error': str(e)
        }
```

### PASSO 3: Modificar Frontend

#### 3.1: Abrir arquivo

```bash
code app.py
```

#### 3.2: Localizar seção de geração

**Linhas ~210-240** - Dentro do `if st.button("🚀 Gerar Contestação"...)`

#### 3.3: Substituir código após processamento RAG

**Após a linha ~240** (depois do processamento RAG), substituir por:

```python
st.success("✅ Processamento concluído!")

# =========================================
# GERAÇÃO COM STREAMING
# =========================================
st.divider()
st.header("📄 Geração da Contestação")

# Containers
status_container = st.empty()
texto_container = st.empty()

# Variáveis
texto_acumulado = ""
metadados_finais = None

# Mostrar status
with status_container.container():
    st.info("🌊 Gerando contestação em tempo real...")

# Obter generator
stream_generator = st.session_state.llm_generator.gerar_contestacao(
    dados_peticao=dados_peticao,
    contexto_rag=contexto_rag,
    temperatura=temperatura,
    top_k=top_k,
    max_tokens=max_tokens,
    stream=True  # 🔥 ATIVAR STREAMING
)

# Processar chunks
for chunk_data in stream_generator:

    # Verificar erro
    if chunk_data.get('error'):
        with status_container.container():
            st.error(f"❌ Erro: {chunk_data['error']}")
        break

    # Processar chunk
    if not chunk_data['done']:
        # Acumular texto
        texto_acumulado += chunk_data['chunk']

        # Atualizar display
        with texto_container.container():
            st.markdown("### 📜 Contestação")
            st.text_area(
                "Texto em geração...",
                value=texto_acumulado,
                height=500,
                label_visibility="collapsed",
                key=f"stream_{len(texto_acumulado)}"  # Key única
            )
    else:
        # Salvar metadados
        metadados_finais = chunk_data.get('metadata')

# Atualizar status final
with status_container.container():
    st.success("✅ Contestação gerada com sucesso!")

# Validar qualidade
with st.spinner("🔍 Validando qualidade..."):
    validacao = st.session_state.validator.validar_contestacao(
        texto_acumulado,
        dados_peticao
    )

# Salvar resultado
st.session_state.resultado = {
    'contestacao': texto_acumulado,
    'dados_peticao': dados_peticao,
    'contexto_rag': contexto_rag,
    'metadados': metadados_finais,
    'validacao': validacao,
    'custo': metadados_finais['custo_estimado']
}

# Mostrar métricas (código existente pode ser mantido)
# ...
```

### PASSO 4: Testar

#### 4.1: Testar backend isoladamente

```python
# Criar arquivo de teste: test_streaming.py
from modules.llm_generator import LLMGenerator

# Dados de teste
dados = {'tipo_caso': 'Teste', 'confianca': 0.9}
contexto = {'nivel_1': [], 'nivel_2': [], 'nivel_3': []}

# Testar streaming
gen = LLMGenerator()
stream = gen.gerar_contestacao(dados, contexto, stream=True)

texto = ""
for chunk_data in stream:
    if not chunk_data['done']:
        texto += chunk_data['chunk']
        print(chunk_data['chunk'], end='', flush=True)
    else:
        print(f"\n\nMetadados: {chunk_data['metadata']}")

print(f"\n\nTexto completo: {len(texto)} caracteres")
```

#### 4.2: Testar frontend completo

```bash
streamlit run app.py
```

---

## 🎨 Melhorias Opcionais

### Opção 1: Adicionar Cursor Piscando

```python
# No texto_container
st.markdown(f"""
<div style="...">
{texto_acumulado}<span style="animation: blink 1s infinite;">▊</span>
</div>

<style>
@keyframes blink {{
    0%, 50% {{ opacity: 1; }}
    51%, 100% {{ opacity: 0; }}
}}
</style>
""", unsafe_allow_html=True)
```

### Opção 2: Toggle no Sidebar

```python
# No sidebar
usar_streaming = st.sidebar.checkbox(
    "🌊 Streaming em Tempo Real",
    value=True,
    help="Mostra texto sendo gerado ao vivo"
)

# Usar na chamada
stream_generator = st.session_state.llm_generator.gerar_contestacao(
    ...,
    stream=usar_streaming  # Usar toggle
)
```

### Opção 3: Barra de Progresso

```python
# Antes do loop
progress_bar = st.progress(0)

# Dentro do loop
progresso = min(len(texto_acumulado) / 10000, 0.99)  # Estimativa
progress_bar.progress(progresso)
```

---

## ⚠️ Problemas Comuns

### Problema 1: Texto não atualiza em tempo real

**Causa**: Key da text_area não está mudando

**Solução**:
```python
st.text_area(
    ...,
    key=f"stream_{len(texto_acumulado)}"  # Key única a cada update
)
```

### Problema 2: Erro "Generator object is not iterable"

**Causa**: Esqueceu de usar `yield` no método streaming

**Solução**: Verificar que `_gerar_com_streaming()` usa `yield`, não `return`

### Problema 3: Metadados None no final

**Causa**: Não processou o último chunk com `done=True`

**Solução**: Garantir que loop processa todos os chunks:
```python
for chunk_data in stream_generator:  # Não usar if/break prematuramente
    ...
```

### Problema 4: Display fica lento com texto grande

**Causa**: Re-renderizar text_area completa a cada chunk é custoso

**Solução**: Usar `st.markdown()` ou limitar frequência de updates:
```python
if len(texto_acumulado) % 100 == 0:  # Atualizar a cada 100 caracteres
    atualizar_display()
```

---

## 📊 Validação

### Checklist de Testes

- [ ] Streaming funciona com petição simples
- [ ] Streaming funciona com petição complexa
- [ ] Texto acumula corretamente
- [ ] Metadados aparecem no final
- [ ] Custo é calculado corretamente
- [ ] Erros são tratados apropriadamente
- [ ] Validação de qualidade funciona após streaming
- [ ] Botões de ação funcionam após geração
- [ ] Download/cópia funcionam com texto gerado
- [ ] Regeneração funciona

### Métricas de Sucesso

- ✅ Texto aparece em < 1 segundo após iniciar
- ✅ Chunks aparecem suavemente (sem travamentos)
- ✅ Metadados corretos ao final
- ✅ Sem erros no console
- ✅ UX melhorou (feedback visual)

---

## 🎯 Resumo

### O que muda:

1. **Backend**: Método `gerar_contestacao()` agora suporta `stream=True`
2. **Frontend**: Loop processa chunks e atualiza UI em tempo real
3. **UX**: Usuário vê texto sendo gerado ao invés de spinner

### O que NÃO muda:

1. ✅ Processamento da petição
2. ✅ Busca RAG
3. ✅ Validação de qualidade
4. ✅ Métricas e estatísticas
5. ✅ Download e cópia

### Compatibilidade:

- ✅ Modo streaming (novo) - `stream=True`
- ✅ Modo tradicional (original) - `stream=False` (padrão)

---

## 📚 Próximos Passos

Após implementação bem-sucedida:

1. [ ] Considerar adicionar opção de "velocidade" do streaming
2. [ ] Implementar cache de chunks (para regeneração parcial)
3. [ ] Adicionar opção de "pausar" geração
4. [ ] Permitir edição em tempo real durante geração
5. [ ] Analytics: medir tempo de geração vs satisfação do usuário

---

**Boa implementação! 🚀**

"""
═══════════════════════════════════════════════════════════════════════════
EXEMPLO: FRONTEND COM STREAMING (app.py)
═══════════════════════════════════════════════════════════════════════════
Este arquivo mostra como a seção de geração do app.py ficaria com streaming

Localização no arquivo original: app.py, linhas ~200-320
"""

import streamlit as st
import time

# =============================================================================
# VERSÃO 1: USANDO st.empty() E ATUALIZAÇÃO MANUAL
# =============================================================================

def gerar_com_streaming_v1():
    """
    Versão 1: Controle manual do streaming com st.empty()

    Vantagens:
    - Controle total sobre a renderização
    - Pode adicionar formatação customizada
    - Funciona em qualquer versão do Streamlit

    Desvantagens:
    - Mais código
    - Precisa gerenciar estado manualmente
    """

    # Dentro do if uploaded_file no app.py
    if st.button("🚀 Gerar Contestação", type="primary", use_container_width=True):

        # Inicializar flag de geração
        st.session_state.gerando = True

        try:
            # =========================================
            # ETAPA 1-3: Processamento (igual ao original)
            # =========================================
            with st.spinner("📄 Processando petição inicial..."):
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

            # =========================================
            # ETAPA 4: GERAÇÃO COM STREAMING (NOVO!)
            # =========================================
            st.divider()
            st.header("📄 Geração da Contestação")

            # Containers para atualização dinâmica
            status_container = st.empty()
            texto_container = st.empty()
            metrics_container = st.empty()

            # Variáveis de acumulação
            texto_acumulado = ""
            metadados_finais = None
            inicio_geracao = time.time()

            # Mostrar status inicial
            with status_container.container():
                st.info("🌊 Gerando contestação em tempo real...")

            # Obter generator de streaming
            stream_generator = st.session_state.llm_generator.gerar_contestacao(
                dados_peticao=dados_peticao,
                contexto_rag=contexto_rag,
                temperatura=temperatura,  # Do sidebar
                top_k=top_k,              # Do sidebar
                max_tokens=max_tokens,    # Do sidebar
                stream=True  # 🔥 ATIVAR STREAMING
            )

            # =========================================
            # PROCESSAR CHUNKS EM TEMPO REAL
            # =========================================
            for chunk_data in stream_generator:

                # Verificar erro
                if chunk_data.get('error'):
                    with status_container.container():
                        st.error(f"❌ Erro na geração: {chunk_data['error']}")
                    break

                # Processar chunk normal
                if not chunk_data['done']:
                    # Acumular texto
                    texto_acumulado += chunk_data['chunk']

                    # Atualizar display em tempo real
                    with texto_container.container():
                        st.markdown("### 📜 Contestação")

                        # Usar markdown para melhor renderização
                        st.markdown(f"""
                        <div style="
                            background-color: #f0f2f6;
                            padding: 20px;
                            border-radius: 10px;
                            border-left: 5px solid #1f77b4;
                            font-family: 'Georgia', serif;
                            line-height: 1.8;
                            max-height: 600px;
                            overflow-y: auto;
                        ">
                        {texto_acumulado}
                        <span style="animation: blink 1s infinite;">▊</span>
                        </div>
                        """, unsafe_allow_html=True)

                        # CSS para animação do cursor
                        st.markdown("""
                        <style>
                        @keyframes blink {
                            0%, 50% { opacity: 1; }
                            51%, 100% { opacity: 0; }
                        }
                        </style>
                        """, unsafe_allow_html=True)

                else:
                    # Último chunk - salvar metadados
                    metadados_finais = chunk_data.get('metadata')

            # Tempo total
            tempo_total = time.time() - inicio_geracao

            # Atualizar status final
            with status_container.container():
                st.success(f"✅ Contestação gerada com sucesso em {tempo_total:.1f}s!")

            # =========================================
            # ETAPA 5: VALIDAÇÃO DE QUALIDADE
            # =========================================
            with st.spinner("🔍 Validando qualidade..."):
                validacao = st.session_state.validator.validar_contestacao(
                    texto_acumulado,
                    dados_peticao
                )

            # =========================================
            # SALVAR RESULTADO NO SESSION STATE
            # =========================================
            st.session_state.resultado = {
                'contestacao': texto_acumulado,
                'dados_peticao': dados_peticao,
                'contexto_rag': contexto_rag,
                'metadados': metadados_finais,
                'validacao': validacao,
                'custo': metadados_finais['custo_estimado']
            }

            # =========================================
            # MOSTRAR MÉTRICAS FINAIS
            # =========================================
            with metrics_container.container():
                st.markdown("### 📊 Métricas")

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric(
                        "Tipo de Caso",
                        dados_peticao.get('tipo_caso', 'N/A')
                    )

                with col2:
                    conf = dados_peticao.get('confianca', 0)
                    st.metric("Confiança", f"{conf:.1%}")

                with col3:
                    st.metric(
                        "Tokens Gerados",
                        f"{metadados_finais['output_tokens']:,}"
                    )

                with col4:
                    st.metric(
                        "Custo",
                        f"${metadados_finais['custo_estimado']:.4f}"
                    )

                # Métricas de qualidade
                if mostrar_metricas:  # Toggle do sidebar
                    st.divider()

                    val = validacao
                    met = val['metricas']

                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.metric("Score Geral", f"{met['score_qualidade']}/100")

                    with col2:
                        st.metric("Classificação", met['classificacao'])

                    with col3:
                        st.metric("Citações Legais", met['citacoes_legais'])

                    with col4:
                        st.metric("Completude", f"{met['completude_estrutural']:.0%}")

                    # Alertas
                    if val['alertas']:
                        st.warning("⚠️ **Alertas:**")
                        for alerta in val['alertas']:
                            st.warning(f"• {alerta}")

            # =========================================
            # BOTÕES DE AÇÃO
            # =========================================
            st.divider()

            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button("📥 Download DOCX", use_container_width=True):
                    # ... lógica de download ...
                    pass

            with col2:
                if st.button("📋 Copiar Texto", use_container_width=True):
                    # ... lógica de cópia ...
                    pass

            with col3:
                if st.button("🔄 Regenerar", use_container_width=True):
                    st.session_state.resultado = None
                    st.rerun()

        except Exception as e:
            st.error(f"❌ Erro: {str(e)}")
            import traceback
            st.code(traceback.format_exc())

        finally:
            st.session_state.gerando = False


# =============================================================================
# VERSÃO 2: USANDO st.write_stream() (MAIS SIMPLES)
# =============================================================================

def gerar_com_streaming_v2():
    """
    Versão 2: Usando st.write_stream() nativo do Streamlit

    Vantagens:
    - Código mais simples e limpo
    - Otimizado pelo Streamlit
    - Menos código para manter

    Desvantagens:
    - Menos controle sobre renderização
    - Requer Streamlit >= 1.29.0
    """

    if st.button("🚀 Gerar Contestação", type="primary", use_container_width=True):

        st.session_state.gerando = True

        try:
            # Processamento (igual v1)
            with st.spinner("📄 Processando petição inicial..."):
                dados_peticao = st.session_state.processor.processar_documento(uploaded_file)
                resultado_rag = st.session_state.rag.buscar_contexto(dados_peticao['fatos_completos'])
                contexto_rag = st.session_state.context_builder.construir_contexto(dados_peticao, resultado_rag)

            st.success("✅ Processamento concluído!")
            st.divider()

            # =========================================
            # STREAMING COM st.write_stream()
            # =========================================
            st.header("📄 Geração da Contestação")

            # Obter generator
            stream_generator = st.session_state.llm_generator.gerar_contestacao(
                dados_peticao=dados_peticao,
                contexto_rag=contexto_rag,
                temperatura=temperatura,
                top_k=top_k,
                max_tokens=max_tokens,
                stream=True
            )

            # Função adapter para st.write_stream()
            def text_stream():
                """Adapter que extrai apenas o texto dos chunks"""
                for chunk_data in stream_generator:
                    if not chunk_data['done'] and not chunk_data.get('error'):
                        yield chunk_data['chunk']
                    elif chunk_data.get('error'):
                        st.error(f"❌ Erro: {chunk_data['error']}")
                        return

            # Exibir streaming (SUPER SIMPLES!)
            st.markdown("### 📜 Contestação")
            texto_acumulado = st.write_stream(text_stream())

            # Salvar no session state
            st.session_state.resultado = {
                'contestacao': texto_acumulado,
                'dados_peticao': dados_peticao,
                # ... resto dos dados ...
            }

            # Métricas e validação (igual v1)
            # ...

        finally:
            st.session_state.gerando = False


# =============================================================================
# VERSÃO 3: STREAMING COM PROGRESS BAR
# =============================================================================

def gerar_com_streaming_v3():
    """
    Versão 3: Com barra de progresso estimada

    Vantagens:
    - Feedback visual de progresso
    - Usuário vê quanto falta
    - Mais profissional

    Desvantagens:
    - Progresso é estimado (não preciso)
    - Mais complexo
    """

    if st.button("🚀 Gerar Contestação", type="primary", use_container_width=True):

        # ... processamento inicial ...

        st.header("📄 Geração da Contestação")

        # Containers
        progress_bar = st.progress(0)
        progress_text = st.empty()
        texto_container = st.empty()

        # Variáveis
        texto_acumulado = ""
        tokens_estimados = max_tokens  # Estimativa
        tokens_gerados = 0

        # Generator
        stream_generator = st.session_state.llm_generator.gerar_contestacao(
            dados_peticao=dados_peticao,
            contexto_rag=contexto_rag,
            stream=True
        )

        # Processar chunks com progresso
        for chunk_data in stream_generator:

            if not chunk_data['done']:
                # Acumular
                chunk_text = chunk_data['chunk']
                texto_acumulado += chunk_text

                # Estimar tokens (rough: ~4 chars = 1 token)
                tokens_gerados += len(chunk_text) / 4

                # Calcular progresso
                progresso = min(tokens_gerados / tokens_estimados, 0.99)

                # Atualizar barra
                progress_bar.progress(progresso)
                progress_text.text(f"Gerando... {progresso*100:.0f}%")

                # Atualizar texto
                with texto_container.container():
                    st.markdown(f"```\n{texto_acumulado}\n```")

            else:
                # Concluído
                progress_bar.progress(1.0)
                progress_text.text("✅ Concluído!")

                metadados_finais = chunk_data['metadata']

        # ... resto do código ...


# =============================================================================
# DICAS DE IMPLEMENTAÇÃO
# =============================================================================

"""
RECOMENDAÇÃO:

Para este projeto, recomendo usar a VERSÃO 1 (st.empty() com controle manual)
porque:

1. Permite adicionar o cursor piscando (melhor UX)
2. Pode formatar o texto como documento legal (fonte serif, espaçamento)
3. Funciona em qualquer versão do Streamlit
4. Dá controle total sobre a renderização

PASSOS PARA IMPLEMENTAR:

1. Copiar o código da Versão 1 acima
2. Substituir a seção de geração no app.py (linhas ~210-320)
3. Modificar o módulo llm_generator.py com o código do EXEMPLO_llm_generator_streaming.py
4. Testar com uma petição real
5. Ajustar estilos e formatação conforme necessário

OPCIONAL - MELHORIAS FUTURAS:

- Adicionar botão "Pausar/Retomar" durante geração
- Salvar chunks parciais em caso de erro
- Permitir editar texto em tempo real
- Adicionar modo "rápido" vs "detalhado"
"""

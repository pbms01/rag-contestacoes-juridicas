"""
═══════════════════════════════════════════════════════════════════════════
EXEMPLO: LLM GENERATOR COM SUPORTE A STREAMING
═══════════════════════════════════════════════════════════════════════════
Este arquivo mostra como o módulo llm_generator.py ficaria com streaming
"""

import os
from typing import Dict, List, Optional, Generator, Union
import anthropic

from config.settings import Config
from config.prompts import SYSTEM_PROMPT, construir_prompt_usuario

class LLMGenerator:
    """Gera contestação usando Claude API com suporte a streaming"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Inicializa gerador

        Args:
            api_key: Chave API Anthropic (usa variável de ambiente se None)
        """
        self.api_key = api_key or Config.ANTHROPIC_API_KEY

        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY não encontrada. "
                "Configure a variável de ambiente ou passe como parâmetro."
            )

        self.client = anthropic.Anthropic(api_key=self.api_key)

    def gerar_contestacao(
        self,
        dados_peticao: Dict,
        contexto_rag: Dict,
        temperatura: float = Config.DEFAULT_TEMPERATURE,
        top_k: int = Config.DEFAULT_TOP_K,
        max_tokens: int = Config.DEFAULT_MAX_TOKENS,
        stream: bool = False  # NOVO PARÂMETRO
    ) -> Union[Dict, Generator]:
        """
        Gera contestação via Claude API

        Args:
            dados_peticao: Dados estruturados da petição
            contexto_rag: Contexto RAG construído
            temperatura: Parâmetro de temperatura (0.3-0.9)
            top_k: Parâmetro top-k (20-60)
            max_tokens: Tokens máximos para geração
            stream: Se True, retorna generator com chunks; se False, retorna Dict completo

        Returns:
            Se stream=False: Dict com contestação gerada e metadados
            Se stream=True: Generator que yielda chunks de texto
        """
        print("\n" + "="*80)
        print("🤖 GERANDO CONTESTAÇÃO COM CLAUDE SONNET 4.5")
        print("="*80 + "\n")

        # Validar parâmetros
        temperatura = max(Config.MIN_TEMPERATURE, min(temperatura, Config.MAX_TEMPERATURE))
        top_k = max(Config.MIN_TOP_K, min(top_k, Config.MAX_TOP_K))

        print(f"⚙️  Parâmetros:")
        print(f"   Temperatura: {temperatura}")
        print(f"   Top-k: {top_k}")
        print(f"   Max tokens: {max_tokens}")
        print(f"   Streaming: {'Ativado' if stream else 'Desativado'}\n")

        # Construir prompts
        print("📝 Construindo prompts...")
        prompt_usuario = construir_prompt_usuario(dados_peticao, contexto_rag)

        # Estimar tokens (aproximado)
        tokens_estimados = (len(SYSTEM_PROMPT) + len(prompt_usuario)) // 4
        print(f"   Tokens estimados (input): ~{tokens_estimados:,}\n")

        # NOVA LÓGICA: Escolher entre streaming ou não
        if stream:
            print("🌊 Modo STREAMING ativado")
            return self._gerar_com_streaming(
                prompt_usuario=prompt_usuario,
                temperatura=temperatura,
                top_k=top_k,
                max_tokens=max_tokens,
                dados_peticao=dados_peticao
            )
        else:
            print("📦 Modo TRADICIONAL ativado")
            return self._gerar_sem_streaming(
                prompt_usuario=prompt_usuario,
                temperatura=temperatura,
                top_k=top_k,
                max_tokens=max_tokens,
                dados_peticao=dados_peticao
            )

    def _gerar_sem_streaming(
        self,
        prompt_usuario: str,
        temperatura: float,
        top_k: int,
        max_tokens: int,
        dados_peticao: Dict
    ) -> Dict:
        """
        Gera contestação de forma tradicional (sem streaming)

        Este é o método original - mantido para compatibilidade
        """
        print("🌐 Chamando API Claude...")
        try:
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

            # Extrair resposta
            contestacao_texto = response.content[0].text

            # Metadados da geração
            metadados = {
                'model': Config.CLAUDE_MODEL,
                'temperatura': temperatura,
                'top_k': top_k,
                'input_tokens': response.usage.input_tokens,
                'output_tokens': response.usage.output_tokens,
                'stop_reason': response.stop_reason,
                'tipo_caso': dados_peticao.get('tipo_caso'),
                'confianca_classificacao': dados_peticao.get('confianca')
            }

            print(f"✅ Geração concluída!")
            print(f"   Input tokens: {metadados['input_tokens']:,}")
            print(f"   Output tokens: {metadados['output_tokens']:,}")
            print(f"   Total tokens: {metadados['input_tokens'] + metadados['output_tokens']:,}\n")

            # Custo estimado (aproximado para Sonnet 4.5)
            custo_input = (metadados['input_tokens'] / 1_000_000) * 15  # $15/MTok
            custo_output = (metadados['output_tokens'] / 1_000_000) * 75  # $75/MTok
            custo_total = custo_input + custo_output

            print(f"💰 Custo estimado: ${custo_total:.4f}\n")

            print("="*80)
            print("✅ CONTESTAÇÃO GERADA COM SUCESSO")
            print("="*80 + "\n")

            return {
                'contestacao': contestacao_texto,
                'metadados': metadados,
                'custo_estimado': custo_total,
                'sucesso': True
            }

        except anthropic.APIError as e:
            print(f"❌ Erro na API: {e}\n")
            return {
                'contestacao': None,
                'erro': str(e),
                'sucesso': False
            }
        except Exception as e:
            print(f"❌ Erro inesperado: {e}\n")
            return {
                'contestacao': None,
                'erro': str(e),
                'sucesso': False
            }

    def _gerar_com_streaming(
        self,
        prompt_usuario: str,
        temperatura: float,
        top_k: int,
        max_tokens: int,
        dados_peticao: Dict
    ) -> Generator[Dict, None, None]:
        """
        NOVO MÉTODO: Gera contestação com streaming

        Yields:
            Dict contendo:
            - 'chunk': Texto do chunk atual (string)
            - 'done': Boolean indicando se a geração terminou
            - 'metadata': Metadados completos (apenas no último chunk)
            - 'error': Mensagem de erro (se houver)
        """
        print("🌐 Iniciando streaming da API Claude...")

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

                print("🌊 Streaming iniciado! Yielding chunks...\n")

                # Contador de chunks (para debug)
                chunk_count = 0

                # Iterar sobre os eventos de streaming
                for text in stream.text_stream:
                    chunk_count += 1

                    # Yield cada chunk de texto
                    yield {
                        'chunk': text,
                        'done': False,
                        'metadata': None,
                        'error': None
                    }

                print(f"\n✅ Streaming concluído! Total de chunks: {chunk_count}")

                # Obter mensagem final com metadados
                final_message = stream.get_final_message()

                # Construir metadados
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

                # Calcular custo estimado
                custo_input = (metadados['input_tokens'] / 1_000_000) * 15  # $15/MTok
                custo_output = (metadados['output_tokens'] / 1_000_000) * 75  # $75/MTok
                custo_total = custo_input + custo_output

                metadados['custo_estimado'] = custo_total

                print(f"   Input tokens: {metadados['input_tokens']:,}")
                print(f"   Output tokens: {metadados['output_tokens']:,}")
                print(f"   Total tokens: {metadados['input_tokens'] + metadados['output_tokens']:,}")
                print(f"   Custo estimado: ${custo_total:.4f}\n")

                print("="*80)
                print("✅ CONTESTAÇÃO GERADA COM SUCESSO (STREAMING)")
                print("="*80 + "\n")

                # Último chunk com metadados completos
                yield {
                    'chunk': '',  # Vazio - apenas metadados
                    'done': True,
                    'metadata': metadados,
                    'error': None
                }

        except anthropic.APIError as e:
            print(f"❌ Erro na API durante streaming: {e}\n")
            yield {
                'chunk': '',
                'done': True,
                'metadata': None,
                'error': f"Erro na API: {str(e)}"
            }

        except Exception as e:
            print(f"❌ Erro inesperado durante streaming: {e}\n")
            yield {
                'chunk': '',
                'done': True,
                'metadata': None,
                'error': f"Erro inesperado: {str(e)}"
            }

    def regenerar_com_ajustes(
        self,
        resultado_anterior: Dict,
        ajustes: str,
        temperatura: Optional[float] = None,
        top_k: Optional[int] = None
    ) -> Dict:
        """
        Regenera contestação com ajustes solicitados pelo usuário

        Args:
            resultado_anterior: Resultado da geração anterior
            ajustes: Instruções de ajuste do usuário
            temperatura: Nova temperatura (opcional)
            top_k: Novo top-k (opcional)

        Returns:
            Nova contestação gerada
        """
        # TODO: Implementar funcionalidade de regeneração com feedback
        pass


# =============================================================================
# EXEMPLO DE USO
# =============================================================================

if __name__ == "__main__":
    """
    Exemplo de como usar o gerador com streaming
    """

    # Dados de exemplo (simplificados)
    dados_peticao = {
        'tipo_caso': 'Indenização por Danos Morais',
        'confianca': 0.92,
        'fatos_completos': 'Teste de fatos...'
    }

    contexto_rag = {
        'nivel_1': [],
        'nivel_2': [],
        'nivel_3': []
    }

    # Inicializar gerador
    generator = LLMGenerator()

    print("\n" + "="*80)
    print("TESTE: STREAMING")
    print("="*80 + "\n")

    # Gerar com streaming
    stream = generator.gerar_contestacao(
        dados_peticao=dados_peticao,
        contexto_rag=contexto_rag,
        stream=True  # ATIVAR STREAMING
    )

    # Acumular texto
    texto_completo = ""
    metadados_finais = None

    for chunk_data in stream:
        if chunk_data.get('error'):
            print(f"ERRO: {chunk_data['error']}")
            break

        if not chunk_data['done']:
            # Acumular chunk
            texto_completo += chunk_data['chunk']

            # Mostrar chunk (simulando streaming)
            print(chunk_data['chunk'], end='', flush=True)
        else:
            # Salvar metadados finais
            metadados_finais = chunk_data.get('metadata')

    print("\n\n" + "="*80)
    print(f"TEXTO FINAL: {len(texto_completo)} caracteres")
    print(f"METADADOS: {metadados_finais}")
    print("="*80)

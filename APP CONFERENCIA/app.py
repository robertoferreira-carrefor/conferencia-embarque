import streamlit as st
import pandas as pd
from pyzbar.pyzbar import decode
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import re
import io


# ============================================================
# CONFIGURAÇÃO
# ============================================================

st.set_page_config(
    page_title="Conferência de Embarque em Lote",
    page_icon="📦",
    layout="centered"
)

st.title("📦 Conferência de Embarque (Múltiplas Etiquetas)")
st.write(
    "Envie várias fotos de etiquetas de uma vez para consultar "
    "a situação de todas elas no relatório."
)


# ============================================================
# FUNÇÕES
# ============================================================

def normalizar_texto(valor):
    """
    Deixa o texto em um formato padrão para comparação.
    Remove espaços, pontos de números, zeros à esquerda e coloca em maiúsculo.
    """
    if pd.isna(valor):
        return ""

    texto = str(valor).strip().upper()

    # Remove .0 de números vindos do Excel
    texto = re.sub(r"\.0$", "", texto)

    # Remove espaços
    texto = texto.replace(" ", "")

    # Remove zeros à esquerda (ex: "00254" vira "254" para bater com o Excel)
    texto = texto.lstrip("0")

    # Se por acaso a tarefa for literalmente "0", garante que não fique vazio
    if texto == "":
        texto = "0"

    return texto


def ler_codigo(imagem):
    """
    Tenta ler o código de barras de várias formas.
    """
    imagens = []

    # Imagem original
    imagens.append(imagem)

    # Escala de cinza
    cinza = ImageOps.grayscale(imagem)
    imagens.append(cinza)

    # Contraste maior
    contraste = ImageEnhance.Contrast(cinza).enhance(2.0)
    imagens.append(contraste)

    # Nitidez
    nitidez = contraste.filter(ImageFilter.SHARPEN)
    imagens.append(nitidez)

    # Aumenta a imagem
    largura, altura = imagem.size

    if largura < 1500:
        fator = 2
        maior = imagem.resize(
            (largura * fator, altura * fator)
        )
        imagens.append(maior)

        maior_cinza = ImageOps.grayscale(maior)
        imagens.append(maior_cinza)

    # Tenta ler todas as versões
    for img in imagens:
        try:
            codigos = decode(img)

            if codigos:
                for codigo in codigos:
                    try:
                        texto = codigo.data.decode(
                            "utf-8",
                            errors="ignore"
                        ).strip()

                        if texto:
                            return texto

                    except Exception:
                        continue

        except Exception:
            continue

    return None


def interpretar_etiqueta(codigo):
    """
    Interpreta o código da etiqueta e separa a Tarefa do Tipo.

    Exemplo da sua etiqueta:
    TF400126092620033G

    TF        = prefixo
    4001      = loja
    260926    = data
    20033     = tarefa (números)
    G         = tipo (letra no final)
    """
    codigo_limpo = normalizar_texto(codigo)

    # Formato principal: TF + 4 dígitos (loja) + 6 dígitos (data) + números + 1 letra (tipo)
    padrao = re.match(
        r"^TF(\d{4})(\d{6})(\d+)([A-Z])$",
        codigo_limpo
    )

    if padrao:
        loja = padrao.group(1)
        data = padrao.group(2)
        tarefa = padrao.group(3)
        tipo = padrao.group(4)

        return {
            "loja": loja,
            "data": data,
            "tarefa": tarefa,
            "tipo": tipo,
            "codigo": codigo_limpo
        }

    return None


def encontrar_coluna(df, nomes):
    """
    Procura automaticamente uma coluna pelos nomes possíveis.
    """
    colunas_normalizadas = {}

    for coluna in df.columns:
        chave = (
            str(coluna)
            .strip()
            .upper()
            .replace(" ", "")
            .replace("_", "")
        )
        colunas_normalizadas[chave] = coluna

    for nome in nomes:
        chave = (
            nome
            .strip()
            .upper()
            .replace(" ", "")
            .replace("_", "")
        )

        if chave in colunas_normalizadas:
            return colunas_normalizadas[chave]

    return None


# ============================================================
# SIDEBAR - RELATÓRIO
# ============================================================

st.sidebar.header("📁 Relatório da Empresa")

arquivo = st.sidebar.file_uploader(
    "Envie o relatório",
    type=["xlsx", "xls", "csv"]
)

df = None

if arquivo is not None:
    try:
        if arquivo.name.lower().endswith(".csv"):
            try:
                df = pd.read_csv(
                    arquivo,
                    encoding="utf-8"
                )
            except UnicodeDecodeError:
                arquivo.seek(0)
                df = pd.read_csv(
                    arquivo,
                    encoding="latin1",
                    sep=None,
                    engine="python"
                )
        else:
            df = pd.read_excel(arquivo)

        st.sidebar.success("✅ Relatório carregado!")
        st.sidebar.write(f"*Linhas:* {len(df)}")
        st.sidebar.write("*Colunas encontradas:*")

        for coluna in df.columns:
            st.sidebar.code(str(coluna))

    except Exception as erro:
        st.sidebar.error(f"Erro ao abrir o relatório:\n{erro}")
        df = None


# ============================================================
# CONFIGURAÇÃO DAS COLUNAS
# ============================================================

if df is not None:
    st.sidebar.divider()
    st.sidebar.header("⚙️ Colunas do relatório")

    # Tenta descobrir automaticamente
    coluna_loja_auto = encontrar_coluna(
        df, ["LOJA", "NUMERO LOJA", "Nº LOJA", "NR LOJA", "CLUBE", "COD LOJA"]
    )

    coluna_tarefa_auto = encontrar_coluna(
        df, ["TRF", "TAREFA", "TAREFA/BOLETIM", "BOLETIM", "TRF/BOLETIM"]
    )

    coluna_tipo_auto = encontrar_coluna(
        df, ["TIPO", "TP", "TIPO TAREFA"]
    )

    coluna_situacao_auto = encontrar_coluna(
        df, ["SITUACAO", "SITUAÇÃO", "STATUS", "STATUS EMBARQUE"]
    )

    # Lista para seleção
    colunas = list(df.columns)

    # Loja
    indice_loja = colunas.index(coluna_loja_auto) if coluna_loja_auto in colunas else 0
    coluna_loja = st.sidebar.selectbox("🏪 Coluna da Loja", colunas, index=indice_loja)

    # Tarefa
    indice_tarefa = colunas.index(coluna_tarefa_auto) if coluna_tarefa_auto in colunas else 0
    coluna_tarefa = st.sidebar.selectbox("📋 Coluna da Tarefa", colunas, index=indice_tarefa)

    # Tipo
    indice_tipo = colunas.index(coluna_tipo_auto) if coluna_tipo_auto in colunas else 0
    coluna_tipo = st.sidebar.selectbox("🏷️ Coluna do Tipo", colunas, index=indice_tipo)

    # Situação
    indice_situacao = colunas.index(coluna_situacao_auto) if coluna_situacao_auto in colunas else 0
    coluna_situacao = st.sidebar.selectbox("📊 Coluna da Situação", colunas, index=indice_situacao)


# ============================================================
# SEM RELATÓRIO
# ============================================================

if df is None:
    st.info("👈 Primeiro envie o relatório da empresa pelo menu lateral.")
    st.stop()


# ============================================================
# PREPARAÇÃO DO RELATÓRIO
# ============================================================

df["_LOJA_BUSCA"] = df[coluna_loja].apply(normalizar_texto)
df["_TAREFA_BUSCA"] = df[coluna_tarefa].apply(normalizar_texto)
df["_TIPO_BUSCA"] = df[coluna_tipo].apply(normalizar_texto)


# ============================================================
# ÁREA DE UPLOAD DE MÚLTIPLAS FOTOS
# ============================================================

st.divider()
st.subheader("📸 Enviar Fotos das Etiquetas (Lote)")
st.write("Selecione **várias fotos** da sua galeria de uma vez só para consultar todas juntas.")

fotos_enviadas = st.file_uploader(
    "Escolha as fotos das etiquetas",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True,
    key="fotos_lote"
)


# ============================================================
# PROCESSAMENTO DO LOTE
# ============================================================

if fotos_enviadas:
    st.divider()
    st.subheader("📊 Resultados da Consulta em Lote")
    
    resultados_lote = []
    
    with st.spinner(f"🔍 Processando {len(fotos_enviadas)} foto(s)..."):
        for arquivo_foto in fotos_enviadas:
            try:
                imagem = Image.open(arquivo_foto)
                codigo = ler_codigo(imagem)
                
                if not codigo:
                    resultados_lote.append({
                        "Foto": arquivo_foto.name,
                        "Código": "Não lido",
                        "Loja": "-",
                        "Tarefa": "-",
                        "Tipo": "-",
                        "Situação": "❌ Código de barras não encontrado"
                    })
                    continue
                    
                dados = interpretar_etiqueta(codigo)
                
                if not dados:
                    resultados_lote.append({
                        "Foto": arquivo_foto.name,
                        "Código": codigo,
                        "Loja": "-",
                        "Tarefa": "-",
                        "Tipo": "-",
                        "Situação": "⚠️ Formato não reconhecido"
                    })
                    continue
                    
                loja = dados["loja"]
                tarefa = dados["tarefa"]
                tipo = dados["tipo"]
                
                loja_busca = normalizar_texto(loja)
                tarefa_busca = normalizar_texto(tarefa)
                tipo_busca = normalizar_texto(tipo)
                
                resultado = df[
                    (df["_LOJA_BUSCA"] == loja_busca) &
                    (df["_TAREFA_BUSCA"] == tarefa_busca) &
                    (df["_TIPO_BUSCA"] == tipo_busca)
                ]
                
                if not resultado.empty:
                    situacoes = ", ".join(resultado[coluna_situacao].dropna().astype(str).str.strip().unique())
                    resultados_lote.append({
                        "Foto": arquivo_foto.name,
                        "Código": codigo,
                        "Loja": loja,
                        "Tarefa": tarefa,
                        "Tipo": tipo,
                        "Situação": situacoes if situacoes else "⚠️ Situação Vazia"
                    })
                else:
                    resultados_lote.append({
                        "Foto": arquivo_foto.name,
                        "Código": codigo,
                        "Loja": loja,
                        "Tarefa": tarefa,
                        "Tipo": tipo,
                        "Situação": "❌ Não encontrada no relatório"
                    })
                    
            except Exception as e:
                resultados_lote.append({
                    "Foto": arquivo_foto.name,
                    "Código": "Erro",
                    "Loja": "-",
                    "Tarefa": "-",
                    "Tipo": "-",
                    "Situação": f"Erro: {str(e)}"
                })
    
    # Exibe a tabela consolidada com os resultados
    df_resultado = pd.DataFrame(resultados_lote)
    st.dataframe(df_resultado, use_container_width=True, hide_index=True)
    
    # Métricas rápidas de resumo
    st.write("---")
    total_enviadas = len(fotos_enviadas)
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total de Fotos Analisadas", total_enviadas)
    with col2:
        sucessos = sum(1 for r in resultados_lote if "❌" not in r["Situação"] and "⚠️" not in r["Situação"])
        st.metric("Consultas Bem-Sucedidas", sucessos)


# ============================================================
# RODAPÉ
# ============================================================
st.divider()
st.caption("📦 Conferência de Embarque • Consulta baseada no relatório enviado")
import streamlit as st
import pandas as pd
import plotly.express as px
import datetime

# ----------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# ----------------------------------------------------
st.set_page_config(page_title="Painel de Faturamento", layout="wide", initial_sidebar_state="expanded")

# ----------------------------------------------------
# ESTILIZAÇÃO VISUAL 
# ----------------------------------------------------
st.markdown("""
<style>
    div[data-testid="stMetric"] {
        background-color: #2c3e50;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0px 4px 10px rgba(0, 0, 0, 0.2);
        border-left: 6px solid #3498db;
    }
    div[data-testid="stMetricLabel"] p {
        font-size: 1.1rem !important;
        color: #ecf0f1 !important;
        font-weight: 600;
    }
    div[data-testid="stMetricValue"] {
        color: #ffffff !important;
    }
</style>
""", unsafe_allow_html=True)

# ----------------------------------------------------
# 1. CONEXÃO E LIMPEZA DOS DADOS
# ----------------------------------------------------
@st.cache_data(ttl=60)
def carregar_dados():
    sheet_id = "1NHQWWv1TOnlX4YmKM0zZzIz4DwGt1yj1fd7snt_LFuk"
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    
    df = pd.read_csv(url)
    df.columns = df.columns.str.strip()

    def limpar_moeda(val):
        if pd.isna(val): return 0.0
        val_str = str(val).strip().replace('R$', '').strip()
        if not val_str: return 0.0
        
        if '.' in val_str and ',' in val_str:
            val_str = val_str.replace('.', '').replace(',', '.')
        elif ',' in val_str:
            val_str = val_str.replace(',', '.')
            
        try:
            return float(val_str)
        except:
            return 0.0

    if 'Valor_Faturamento' in df.columns:
        df['Valor_Faturamento'] = df['Valor_Faturamento'].apply(limpar_moeda)
    else:
        df['Valor_Faturamento'] = 0.0

    col_vencimento = 'Data _Vencimento' if 'Data _Vencimento' in df.columns else 'Data_Vencimento'
    colunas_data = ['Fim_Medição', 'Data_Faturamento', col_vencimento]
    for col in colunas_data:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce')
        
    if 'Data_Faturamento' in df.columns and 'Fim_Medição' in df.columns:
        df['Tempo'] = (df['Data_Faturamento'] - df['Fim_Medição']).dt.days
        
    if col_vencimento in df.columns and 'Data_Faturamento' in df.columns:
        df['Fat x Venc'] = (df[col_vencimento] - df['Data_Faturamento']).dt.days
    
    if 'Data_Faturamento' in df.columns:
        df['Mes_Ano_Faturamento'] = df['Data_Faturamento'].dt.strftime('%m/%Y').fillna('Sem Data')
    if col_vencimento in df.columns:
        df['Mes_Ano_Vencimento'] = df[col_vencimento].dt.strftime('%m/%Y').fillna('Sem Data')
    
    colunas_texto = ['Restaurante', 'Cliente', 'Validação_Cliente', 'Medição_Encerrada', 'Carteira']
    for col in colunas_texto:
        if col in df.columns:
            df[col] = df[col].fillna('Não Informado').astype(str)
            
    def classificar_validacao(row):
        carteira = str(row.get('Carteira', '')).strip()
        
        if carteira == 'Sem Funcionamento':
            return '🚫 Sem Funcionamento'
            
        fim_med = row.get('Fim_Medição')
        encerrada = str(row.get('Medição_Encerrada', '')).strip()
        hoje = pd.Timestamp.today()
        
        if (pd.notna(fim_med) and hoje < fim_med) or (encerrada.lower() == 'ok'):
            return '⏳ Aguardando encerramento'
            
        dt_fat = row.get('Data_Faturamento')
        dt_venc = row.get(col_vencimento)
        valor = row.get('Valor_Faturamento', 0.0)
        
        carteira_preenchida = carteira not in ['Não Informado', '', 'nan', 'None']
        fat_preenchido = pd.notna(dt_fat)
        venc_preenchido = pd.notna(dt_venc)
        valor_preenchido = valor > 0.0
        
        if fat_preenchido and venc_preenchido and valor_preenchido and carteira_preenchida:
            return '✅ Concluído'
        else:
            return '⚠️ Pendente'
            
    df['Validação'] = df.apply(classificar_validacao, axis=1)
            
    return df

try:
    df_original = carregar_dados()
except Exception as e:
    st.error(f"Erro ao ler a planilha: {e}")
    st.stop()

# ----------------------------------------------------
# 2. FILTROS
# ----------------------------------------------------
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=80)
st.sidebar.title("Filtros do Painel")

def obter_limites_data(coluna):
    if coluna in df_original.columns:
        datas_validas = df_original[coluna].dropna()
        if not datas_validas.empty:
            return datas_validas.min().date(), datas_validas.max().date()
    hoje = datetime.date.today()
    return hoje, hoje

min_fech, max_fech = obter_limites_data('Fim_Medição')
min_fat, max_fat = obter_limites_data('Data_Faturamento')
col_venc = 'Data _Vencimento' if 'Data _Vencimento' in df_original.columns else 'Data_Vencimento'
min_venc, max_venc = obter_limites_data(col_venc)

st.sidebar.markdown("### 📅 Períodos (Datas)")

filtro_fechamento = st.sidebar.date_input("Data de Fechamento", value=(min_fech, max_fech), format="DD/MM/YYYY")
filtro_fat = st.sidebar.date_input("Período de Faturamento", value=(min_fat, max_fat), format="DD/MM/YYYY")
filtro_venc = st.sidebar.date_input("Período de Vencimento", value=(min_venc, max_venc), format="DD/MM/YYYY")

st.sidebar.markdown("### 📋 Categorias")
def pegar_unicos(coluna):
    if coluna in df_original.columns:
        return sorted([x for x in df_original[coluna].unique() if x != 'Não Informado' and x != 'Sem Data'])
    return []

filtro_restaurante = st.sidebar.multiselect("🍽️ Restaurante", pegar_unicos('Restaurante'))
filtro_cliente = st.sidebar.multiselect("🏢 Cliente", pegar_unicos('Cliente'))
filtro_validacao = st.sidebar.multiselect("✅ Validação", pegar_unicos('Validação'))
filtro_encerrado = st.sidebar.multiselect("🔒 Encerrado", pegar_unicos('Medição_Encerrada'))
filtro_carteira = st.sidebar.multiselect("💼 Carteira", pegar_unicos('Carteira'))

# Aplicando os filtros no Dataframe
df_filtrado = df_original.copy()

if len(filtro_fechamento) == 2:
    if filtro_fechamento[0] != min_fech or filtro_fechamento[1] != max_fech:
        df_filtrado = df_filtrado[df_filtrado['Fim_Medição'].notna() & 
                                  (df_filtrado['Fim_Medição'].dt.date >= filtro_fechamento[0]) & 
                                  (df_filtrado['Fim_Medição'].dt.date <= filtro_fechamento[1])]

if len(filtro_fat) == 2:
    if filtro_fat[0] != min_fat or filtro_fat[1] != max_fat:
        df_filtrado = df_filtrado[df_filtrado['Data_Faturamento'].notna() & 
                                  (df_filtrado['Data_Faturamento'].dt.date >= filtro_fat[0]) & 
                                  (df_filtrado['Data_Faturamento'].dt.date <= filtro_fat[1])]

if len(filtro_venc) == 2:
    if filtro_venc[0] != min_venc or filtro_venc[1] != max_venc:
        df_filtrado = df_filtrado[df_filtrado[col_venc].notna() & 
                                  (df_filtrado[col_venc].dt.date >= filtro_venc[0]) & 
                                  (df_filtrado[col_venc].dt.date <= filtro_venc[1])]

if filtro_restaurante: df_filtrado = df_filtrado[df_filtrado['Restaurante'].isin(filtro_restaurante)]
if filtro_cliente: df_filtrado = df_filtrado[df_filtrado['Cliente'].isin(filtro_cliente)]
if filtro_validacao: df_filtrado = df_filtrado[df_filtrado['Validação'].isin(filtro_validacao)]
if filtro_encerrado: df_filtrado = df_filtrado[df_filtrado['Medição_Encerrada'].isin(filtro_encerrado)]
if filtro_carteira: df_filtrado = df_filtrado[df_filtrado['Carteira'].isin(filtro_carteira)]

# ----------------------------------------------------
# 3. PAINEL PRINCIPAL & KPIs
# ----------------------------------------------------
st.title("📊 Painel Gerencial de Faturamento")
st.markdown("---")

if df_filtrado.empty:
    st.warning("⚠️ Nenhum dado encontrado na planilha ou para os filtros selecionados.")
else:
    faturamento_total = df_filtrado['Valor_Faturamento'].sum()
    
    # --- AJUSTE: Contagem considerando apenas onde o Valor foi preenchido (> 0) ---
    contagem_medicoes = df_filtrado[df_filtrado['Valor_Faturamento'] > 0].shape[0]
    
    # --- AJUSTE: Ticket Médio é Faturamento Total dividido pelo Total de Medições ---
    faturamento_medio = (faturamento_total / contagem_medicoes) if contagem_medicoes > 0 else 0.0

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("💰 Faturamento Total", f"R$ {faturamento_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    with col2:
        st.metric("📈 Ticket Médio", f"R$ {faturamento_medio:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    with col3:
        st.metric("📋 Total de Medições", contagem_medicoes)

    st.markdown("<br>", unsafe_allow_html=True)

    # ----------------------------------------------------
    # 4. GRÁFICOS
    # ----------------------------------------------------
    def aplicar_estilo_grafico(fig):
        fig.update_layout(
            plot_bgcolor='rgba(0,0,0,0)', 
            paper_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=20, r=20, t=50, b=20)
        )
        fig.update_xaxes(showgrid=False, zeroline=False)
        fig.update_yaxes(showgrid=True, gridcolor='rgba(200, 200, 200, 0.2)', zeroline=False)
        return fig

    col_graf1, col_graf2 = st.columns(2)

    with col_graf1:
        df_cliente = df_filtrado.groupby('Cliente', as_index=False)['Valor_Faturamento'].sum().sort_values('Valor_Faturamento', ascending=True).tail(10)
        fig_cliente = px.bar(df_cliente, x='Valor_Faturamento', y='Cliente', orientation='h', title='Top 10 Faturamento por Cliente', text_auto='.2s', color_discrete_sequence=['#3498db'])
        fig_cliente.update_traces(textposition='outside')
        fig_cliente = aplicar_estilo_grafico(fig_cliente)
        st.plotly_chart(fig_cliente, use_container_width=True)

    with col_graf2:
        df_rest = df_filtrado.groupby('Restaurante', as_index=False)['Valor_Faturamento'].sum().sort_values('Valor_Faturamento', ascending=True).tail(10)
        fig_rest = px.bar(df_rest, x='Valor_Faturamento', y='Restaurante', orientation='h', title='Top 10 Faturamento por Restaurante', text_auto='.2s', color_discrete_sequence=['#e67e22'])
        fig_rest.update_traces(textposition='outside')
        fig_rest = aplicar_estilo_grafico(fig_rest)
        st.plotly_chart(fig_rest, use_container_width=True)

    col_graf3, col_graf4 = st.columns(2)

    with col_graf3:
        if 'Mes_Ano_Faturamento' in df_filtrado.columns:
            df_tempo = df_filtrado[df_filtrado['Mes_Ano_Faturamento'] != 'Sem Data']
            df_tempo = df_tempo.groupby('Mes_Ano_Faturamento', as_index=False)['Valor_Faturamento'].sum()
            df_tempo['Data_Ordenacao'] = pd.to_datetime(df_tempo['Mes_Ano_Faturamento'], format='%m/%Y', errors='coerce')
            df_tempo = df_tempo.sort_values('Data_Ordenacao')
            
            fig_tempo = px.area(df_tempo, x='Mes_Ano_Faturamento', y='Valor_Faturamento', title='Evolução por Mês/Ano', markers=True, color_discrete_sequence=['#2ecc71'])
            fig_tempo.update_traces(line_shape='spline')
            fig_tempo = aplicar_estilo_grafico(fig_tempo)
            st.plotly_chart(fig_tempo, use_container_width=True)

    with col_graf4:
        if 'Mes_Ano_Faturamento' in df_filtrado.columns and 'Carteira' in df_filtrado.columns:
            df_carteira = df_filtrado[df_filtrado['Mes_Ano_Faturamento'] != 'Sem Data']
            df_carteira = df_carteira.groupby(['Mes_Ano_Faturamento', 'Carteira'], as_index=False)['Valor_Faturamento'].sum()
            df_carteira['Data_Ordenacao'] = pd.to_datetime(df_carteira['Mes_Ano_Faturamento'], format='%m/%Y', errors='coerce')
            df_carteira = df_carteira.sort_values('Data_Ordenacao')
            
            fig_carteira = px.line(df_carteira, x='Mes_Ano_Faturamento', y='Valor_Faturamento', color='Carteira', title='Evolução por Carteira', markers=True)
            fig_carteira.update_traces(line_shape='spline', line=dict(width=3))
            fig_carteira = aplicar_estilo_grafico(fig_carteira)
            st.plotly_chart(fig_carteira, use_container_width=True)

    # ----------------------------------------------------
    # 5. TABELA DE DETALHAMENTO
    # ----------------------------------------------------
    st.markdown("### 📋 Tabela de Dados")
    df_exibicao = df_filtrado.copy()

    cols = list(df_exibicao.columns)
    if 'Tempo' in cols: cols.remove('Tempo')
    if 'Fat x Venc' in cols: cols.remove('Fat x Venc')
    if 'Validação' in cols: cols.remove('Validação')
    
    if 'Data_Faturamento' in cols:
        idx_fat = cols.index('Data_Faturamento')
        if 'Tempo' in df_filtrado.columns:
            cols.insert(idx_fat, 'Tempo')      
            idx_fat += 1                       
        if 'Fat x Venc' in df_filtrado.columns:
            cols.insert(idx_fat + 1, 'Fat x Venc') 

    if 'Fim_Medição' in cols:
        idx_fim = cols.index('Fim_Medição')
        if 'Validação' in df_filtrado.columns:
            cols.insert(idx_fim + 1, 'Validação')

    df_exibicao = df_exibicao[cols]

    colunas_data_exibir = ['Fim_Medição', 'Data_Faturamento', col_venc]

    for col in colunas_data_exibir:
        if col in df_exibicao.columns:
            df_exibicao[col] = df_exibicao[col].dt.strftime('%d/%m/%Y').fillna('-')

    if 'Valor_Faturamento' in df_exibicao.columns:
        df_exibicao['Valor_Faturamento'] = df_exibicao['Valor_Faturamento'].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    if 'Tempo' in df_exibicao.columns:
        df_exibicao['Tempo'] = df_exibicao['Tempo'].apply(lambda x: f"{int(x)}" if pd.notna(x) else "-")
    
    if 'Fat x Venc' in df_exibicao.columns:
        df_exibicao['Fat x Venc'] = df_exibicao['Fat x Venc'].apply(lambda x: f"{int(x)}" if pd.notna(x) else "-")

    st.dataframe(df_exibicao, use_container_width=True, height=800, hide_index=True)
import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
import re
import calendar
import os

# ----------------------------------------------------
# FORÇAR MODO ESCURO NATIVO 
# ----------------------------------------------------
if not os.path.exists('.streamlit'):
    os.makedirs('.streamlit')
with open('.streamlit/config.toml', 'w', encoding='utf-8') as f:
    f.write('[theme]\nbase="dark"\n')

# ----------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# ----------------------------------------------------
st.set_page_config(page_title="Painel de Faturamento", layout="wide", initial_sidebar_state="expanded")

# ----------------------------------------------------
# ESTILIZAÇÃO VISUAL 
# ----------------------------------------------------
st.markdown("""
<style>
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
    }
    
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
    colunas_data = ['Fim_Medição', 'Data_Faturamento', col_vencimento, 'Inicio_Medição']
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
            df[col] = df[col].fillna('Não Informado').astype(str).str.strip()
            
    if 'Carteira' in df.columns:
        df['Carteira'] = df['Carteira'].replace(['Depósito em Conta', 'Deposito em Conta', 'DEPÓSITO EM CONTA'], 'Transferência Bancária')

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

    def validar_vencimento(row):
        venc_real = row.get(col_vencimento)
        dt_fat = row.get('Data_Faturamento')
        fim_med = row.get('Fim_Medição')
        inicio_med = row.get('Inicio_Medição')
        prazo_raw = row.get('Prazo')
        dia_texto = str(row.get('Dia', '')).strip().lower()

        if dia_texto in ['', 'nan', 'none', 'não informado']:
            return '➖ Não Avaliado'

        if pd.notna(venc_real) and pd.notna(dt_fat) and pd.notna(prazo_raw):
            try:
                prazo_match = re.search(r'(\d+)', str(prazo_raw))
                if prazo_match:
                    prazo_dias_limite = int(prazo_match.group(1))
                    prazo_real_executado = (venc_real - dt_fat).days
                    if prazo_real_executado < prazo_dias_limite:
                        return '🚀 Antecipado'
            except:
                pass

        if "antecipado" in dia_texto:
            if pd.isna(dt_fat) or pd.isna(inicio_med):
                return '➖ Não Avaliado'
            return '🚀 Antecipado' if dt_fat < inicio_med else '❌ Não Antecipado'

        dias_semana = {'segunda': 0, 'terça': 1, 'terca': 1, 'quarta': 2, 'quinta': 3, 'sexta': 4, 'sábado': 5, 'sabado': 5, 'domingo': 6}
        for nome_dia, num_dia in dias_semana.items():
            if nome_dia in dia_texto:
                if pd.isna(venc_real): return '➖ Não Avaliado'
                return '✅ Dentro do Prazo' if venc_real.weekday() == num_dia else '❌ Depois do Prazo'

        match = re.search(r'(\d+)', dia_texto)
        if not match: return '➖ Não Avaliado'
        numero_dia = int(match.group(1))

        if numero_dia == 0:
            fat_venc = (venc_real - dt_fat).days if pd.notna(venc_real) and pd.notna(dt_fat) else None
            if fat_venc is None or pd.isna(prazo_raw): return '➖ Não Avaliado'
            p_match = re.search(r'(\d+)', str(prazo_raw))
            if p_match:
                return '✅ Dentro do Prazo' if int(fat_venc) == int(p_match.group(1)) else '❌ Depois do Prazo'
            return '➖ Não Avaliado'

        if pd.isna(venc_real) or pd.isna(fim_med): return '➖ Não Avaliado'

        dia_alvo = numero_dia
        mes_alvo = fim_med.month
        ano_alvo = fim_med.year
        
        if dia_alvo <= fim_med.day:
            mes_alvo += 1
            if mes_alvo > 12:
                mes_alvo = 1; ano_alvo += 1
                
        try:
            ultimo_dia_mes = calendar.monthrange(ano_alvo, mes_alvo)[1]
            data_alvo = pd.Timestamp(year=ano_alvo, month=mes_alvo, day=min(dia_alvo, ultimo_dia_mes))
            v_date = venc_real.date()
            a_date = data_alvo.date()
            if v_date == a_date: return '✅ Dentro do Prazo'
            elif v_date > a_date: return '❌ Depois do Prazo'
            else: return '🚀 Antecipado'
        except:
            return '➖ Erro no Cálculo'

    if 'Dia' in df.columns:
        df['Validação do Vencimento'] = df.apply(validar_vencimento, axis=1)

    return df

try:
    df_original = carregar_dados()
except Exception as e:
    st.error(f"Erro ao ler a planilha: {e}")
    st.stop()

# ----------------------------------------------------
# 2. FILTROS
# ----------------------------------------------------
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

st.sidebar.markdown("### 🏆 Rankings")
ranking_clientes = st.sidebar.selectbox("Ranking Clientes", ["Top 10 Clientes", "Top 5 Clientes", "Top 3 Clientes"])
ranking_restaurantes = st.sidebar.selectbox("Ranking Restaurantes", ["Top 10 Restaurantes", "Top 5 Restaurantes", "Top 3 Restaurantes"])

st.sidebar.markdown("### 📋 Categorias")
def pegar_unicos(coluna):
    if coluna in df_original.columns:
        return sorted([x for x in df_original[coluna].unique() if x != 'Não Informado' and x != 'Sem Data'])
    return []

filtro_restaurante = st.sidebar.multiselect("🍽️ Restaurante", pegar_unicos('Restaurante'))
filtro_cliente = st.sidebar.multiselect("🏢 Cliente", pegar_unicos('Cliente'))
filtro_val_cliente = st.sidebar.multiselect("🤝 Validação Cliente", pegar_unicos('Validação_Cliente'))
filtro_validacao = st.sidebar.multiselect("✅ Validação Geral", pegar_unicos('Validação'))
filtro_val_venc = st.sidebar.multiselect("📆 Validação de Vencimento", pegar_unicos('Validação do Vencimento'))
filtro_encerrado = st.sidebar.multiselect("🔒 Encerrado", pegar_unicos('Medição_Encerrada'))
filtro_carteira = st.sidebar.multiselect("💼 Carteira", pegar_unicos('Carteira'))

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
if filtro_val_cliente: df_filtrado = df_filtrado[df_filtrado['Validação_Cliente'].isin(filtro_val_cliente)]
if filtro_validacao: df_filtrado = df_filtrado[df_filtrado['Validação'].isin(filtro_validacao)]
if filtro_val_venc: df_filtrado = df_filtrado[df_filtrado['Validação do Vencimento'].isin(filtro_val_venc)]
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
    contagem_medicoes = df_filtrado[df_filtrado['Valor_Faturamento'] > 0].shape[0]
    faturamento_medio = (faturamento_total / contagem_medicoes) if contagem_medicoes > 0 else 0.0
    total_clientes = df_filtrado['Cliente'].str.split('-').str[0].str.strip().nunique()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("💰 Faturamento Total", f"R$ {faturamento_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    with col2:
        st.metric("📈 Ticket Médio", f"R$ {faturamento_medio:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    with col3:
        st.metric("📋 Total de Medições", contagem_medicoes)
    with col4:
        st.metric("👥 Total de Clientes", total_clientes)

    st.markdown("<br>", unsafe_allow_html=True)

    # ----------------------------------------------------
    # 4. GRÁFICOS INTERATIVOS
    # ----------------------------------------------------
    def aplicar_estilo_grafico(fig):
        fig.update_layout(
            plot_bgcolor='rgba(0,0,0,0)', 
            paper_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=20, r=20, t=50, b=20)
        )
        fig.update_xaxes(title_text='', showgrid=False, zeroline=False)
        fig.update_yaxes(title_text='', showgrid=True, gridcolor='rgba(200, 200, 200, 0.2)', zeroline=False)
        return fig

    col_graf1, col_graf2 = st.columns(2)

    with col_graf1:
        df_cliente = df_filtrado.groupby('Cliente', as_index=False)['Valor_Faturamento'].sum().sort_values('Valor_Faturamento', ascending=True)
        if ranking_clientes == "Top 10 Clientes": df_cliente = df_cliente.tail(10)
        elif ranking_clientes == "Top 5 Clientes": df_cliente = df_cliente.tail(5)
        elif ranking_clientes == "Top 3 Clientes": df_cliente = df_cliente.tail(3)
        df_cliente['Valor_Formatado'] = df_cliente['Valor_Faturamento'].apply(lambda x: f"<b>R$ {x:,.2f}</b>".replace(",", "X").replace(".", ",").replace("X", "."))
        fig_cliente = px.bar(df_cliente, x='Valor_Faturamento', y='Cliente', orientation='h', title='Faturamento por Cliente', text='Valor_Formatado', color_discrete_sequence=['#3498db'])
        fig_cliente.update_traces(textposition='inside', textfont_size=16, textfont_color='white')
        fig_cliente = aplicar_estilo_grafico(fig_cliente)
        evento_cliente = st.plotly_chart(fig_cliente, use_container_width=True, on_select="rerun")

    with col_graf2:
        df_rest = df_filtrado.groupby('Restaurante', as_index=False)['Valor_Faturamento'].sum().sort_values('Valor_Faturamento', ascending=True)
        if ranking_restaurantes == "Top 10 Restaurantes": df_rest = df_rest.tail(10)
        elif ranking_restaurantes == "Top 5 Restaurantes": df_rest = df_rest.tail(5)
        elif ranking_restaurantes == "Top 3 Restaurantes": df_rest = df_rest.tail(3)
        df_rest['Valor_Formatado'] = df_rest['Valor_Faturamento'].apply(lambda x: f"<b>R$ {x:,.2f}</b>".replace(",", "X").replace(".", ",").replace("X", "."))
        fig_rest = px.bar(df_rest, x='Valor_Faturamento', y='Restaurante', orientation='h', title='Faturamento por Restaurante', text='Valor_Formatado', color_discrete_sequence=['#e67e22'])
        fig_rest.update_traces(textposition='inside', textfont_size=16, textfont_color='white')
        fig_rest = aplicar_estilo_grafico(fig_rest)
        evento_rest = st.plotly_chart(fig_rest, use_container_width=True, on_select="rerun")

    col_graf3, col_graf4 = st.columns(2)

    with col_graf3:
        if 'Mes_Ano_Faturamento' in df_filtrado.columns:
            df_tempo = df_filtrado[df_filtrado['Mes_Ano_Faturamento'] != 'Sem Data'].copy()
            df_tempo['Data_Ordenacao'] = pd.to_datetime(df_tempo['Mes_Ano_Faturamento'], format='%m/%Y', errors='coerce')
            df_tempo = df_tempo.groupby(['Mes_Ano_Faturamento', 'Data_Ordenacao'], as_index=False)['Valor_Faturamento'].sum().sort_values('Data_Ordenacao')
            df_tempo['Valor_Texto'] = df_tempo['Valor_Faturamento'].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            
            fig_tempo = px.area(df_tempo, x='Mes_Ano_Faturamento', y='Valor_Faturamento', title='Evolução por Mês/Ano', markers=True, text='Valor_Texto', color_discrete_sequence=['#2ecc71'])
            fig_tempo.update_traces(line_shape='spline', textposition='top center', textfont=dict(color='white', size=12))
            fig_tempo = aplicar_estilo_grafico(fig_tempo)
            # Garante que o eixo X siga a ordem cronológica
            fig_tempo.update_xaxes(type='category', categoryorder='array', categoryarray=df_tempo['Mes_Ano_Faturamento'])
            evento_tempo = st.plotly_chart(fig_tempo, use_container_width=True, on_select="rerun")

    with col_graf4:
        if 'Mes_Ano_Faturamento' in df_filtrado.columns and 'Carteira' in df_filtrado.columns:
            df_cart_plot = df_filtrado[df_filtrado['Mes_Ano_Faturamento'] != 'Sem Data'].copy()
            df_cart_plot['Data_Ordenacao'] = pd.to_datetime(df_cart_plot['Mes_Ano_Faturamento'], format='%m/%Y', errors='coerce')
            df_cart_plot = df_cart_plot.groupby(['Mes_Ano_Faturamento', 'Data_Ordenacao', 'Carteira'], as_index=False)['Valor_Faturamento'].sum().sort_values('Data_Ordenacao')
            df_cart_plot['Valor_Texto'] = df_cart_plot['Valor_Faturamento'].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            
            fig_carteira = px.line(df_cart_plot, x='Mes_Ano_Faturamento', y='Valor_Faturamento', color='Carteira', title='Evolução por Carteira', markers=True, text='Valor_Texto')
            fig_carteira.update_traces(textposition="top center", line_shape='spline', line=dict(width=3))
            fig_carteira = aplicar_estilo_grafico(fig_carteira)
            fig_carteira.update_xaxes(type='category', categoryorder='array', categoryarray=df_cart_plot['Mes_Ano_Faturamento'].unique())
            evento_carteira = st.plotly_chart(fig_carteira, use_container_width=True, on_select="rerun")

    # ----------------------------------------------------
    # 5. TABELA DE DETALHAMENTO (Com Cross-Filtering)
    # ----------------------------------------------------
    st.markdown("### 📋 Tabela de Dados")
    df_exibicao = df_filtrado.copy()
    
    # Captura seleções dos gráficos
    clientes_sel = [pt['y'] for pt in evento_cliente.selection.get('points', [])] if evento_cliente and evento_cliente.selection else []
    rests_sel = [pt['y'] for pt in evento_rest.selection.get('points', [])] if evento_rest and evento_rest.selection else []
    meses_sel = [pt['x'] for pt in evento_tempo.selection.get('points', [])] if evento_tempo and evento_tempo.selection else []
    carteiras_sel = [pt['customdata'][0] if 'customdata' in pt else None for pt in evento_carteira.selection.get('points', [])] if evento_carteira and evento_carteira.selection else []

    if clientes_sel: df_exibicao = df_exibicao[df_exibicao['Cliente'].isin(clientes_sel)]
    if rests_sel: df_exibicao = df_exibicao[df_exibicao['Restaurante'].isin(rests_sel)]
    if meses_sel: df_exibicao = df_exibicao[df_exibicao['Mes_Ano_Faturamento'].isin(meses_sel)]
    if any(carteiras_sel): df_exibicao = df_exibicao[df_exibicao['Carteira'].isin(carteiras_sel)]

    cols = list(df_exibicao.columns)
    for c in ['Tempo', 'Fat x Venc', 'Validação', 'Validação do Vencimento']:
        if c in cols: cols.remove(c)
    
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

    if col_venc in cols:
        idx_venc = cols.index(col_venc)
        if 'Validação do Vencimento' in df_filtrado.columns:
            cols.insert(idx_venc + 1, 'Validação do Vencimento')

    df_exibicao = df_exibicao[cols]

    # CONFIGURAÇÃO DE COLUNAS: Formata Moeda BR e Datas sem quebrar a ordenação
    config_colunas = {
        "Valor_Faturamento": st.column_config.NumberColumn("Valor Faturamento", format="R$ %.2f"),
        "Fim_Medição": st.column_config.DateColumn("Fim Medição", format="DD/MM/YYYY"),
        "Data_Faturamento": st.column_config.DateColumn("Data Faturamento", format="DD/MM/YYYY"),
        col_venc: st.column_config.DateColumn("Data Vencimento", format="DD/MM/YYYY"),
        "Inicio_Medição": st.column_config.DateColumn("Início Medição", format="DD/MM/YYYY"),
        "Tempo": st.column_config.NumberColumn("Tempo", format="%d dias"),
        "Fat x Venc": st.column_config.NumberColumn("Fat x Venc", format="%d dias")
    }

    st.dataframe(
        df_exibicao, 
        use_container_width=True, 
        height=800, 
        hide_index=True,
        column_config=config_colunas
    )
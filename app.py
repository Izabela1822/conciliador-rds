# app.py — Conciliador Bancário (Streamlit)
import io, re, zipfile, pandas as pd, streamlit as st

st.set_page_config(page_title="Conciliador Bancário", page_icon="💸", layout="wide")
st.title("💸 Conciliador Bancário – RDS")
st.caption("Envie o extrato e os documentos (boletos, comprovantes, notas fiscais) para conciliação automática.")

KEY_PATTERNS = [r'nf\s*\d+', r'nfe?\s*\d+', r'invoice\s*\d+', r'pagamento\s*\d+']
DOC_HINTS = {'nota_fiscal':[r'\bnf\b',r'\bnfe\b','nota fiscal'],'boleto':[r'\bboleto\b'],'comprovante':[r'\bcomprovante\b',r'\bpix\b',r'\brecibo\b']}

def normalize_key(raw): return re.sub(r'[^A-Z0-9]','',raw.upper().replace(' ',''))
def extract_key(text):
    if not isinstance(text,str): return None
    for p in KEY_PATTERNS:
        m = re.search(p,text,flags=re.I)
        if m: return normalize_key(m.group(0))
    return None
def guess_doc_type(name):
    for k,pats in DOC_HINTS.items():
        for p in pats:
            if re.search(p,name,flags=re.I): return k
    return 'outro'

def read_statement(file):
    if file.name.endswith(('.xlsx','.xls')): df=pd.read_excel(file)
    else: df=pd.read_csv(file,sep=None,engine='python')
    df.columns=[c.lower() for c in df.columns]
    date_col=next((c for c in df.columns if 'data' in c),df.columns[0])
    desc_col=next((c for c in df.columns if 'desc' in c or 'hist' in c),df.columns[1])
    val_col=next((c for c in df.columns if 'valor' in c or 'amount' in c),df.columns[-1])
    df['data']=pd.to_datetime(df[date_col],errors='coerce',dayfirst=True)
    df['descricao']=df[desc_col].astype(str)
    df['valor']=pd.to_numeric(df[val_col],errors='coerce')
    return df[['data','descricao','valor']]

def reconcile(statement,docs):
    rows=[]
    for _,r in statement.iterrows():
        desc=str(r['descricao'])
        key=extract_key(desc)
        found=[f for f in docs if key and key in f['key']] if key else []
        tipos=[f['tipo'] for f in found]
        missing=[t for t in ['nota_fiscal','boleto','comprovante'] if t not in tipos]
        rows.append({'Data':r['data'],'Descrição':desc,'Valor':r['valor'],'Chave':key or '-','Docs encontrados':', '.join(tipos) or '-','Faltando':', '.join(missing) or '-'})
    return pd.DataFrame(rows)

with st.sidebar:
    st.header('Uploads')
    extrato=st.file_uploader('Extrato bancário (CSV/XLSX)',type=['csv','xlsx','xls'])
    documentos=st.file_uploader('Documentos (PDFs)',type=None,accept_multiple_files=True)

if extrato is None:
    st.info('Envie o extrato bancário na barra lateral para começar.')
    st.stop()

stmt=read_statement(extrato)
docs_info=[]
if documentos:
    for d in documentos:
        docs_info.append({'nome':d.name,'tipo':guess_doc_type(d.name),'key':extract_key(d.name) or '_SEM_CHAVE','bytes':d.getvalue()})

resultado=reconcile(stmt,docs_info)
st.dataframe(resultado,use_container_width=True)

excel_buf=io.BytesIO()
resultado.to_excel(excel_buf,index=False)
excel_buf.seek(0)

zip_buf=io.BytesIO()
with zipfile.ZipFile(zip_buf,'w') as zf:
    for d in docs_info:
        zf.writestr(f"{d['key']}/{d['tipo']}/{d['nome']}",d['bytes'])
zip_buf.seek(0)

st.download_button('📊 Baixar Excel (Conciliação)',excel_buf,file_name='conciliacao_resultado.xlsx')
st.download_button('📦 Baixar ZIP (Documentos)',zip_buf,file_name='conciliacao_documentos.zip')
st.caption("Dica: padronize nomes como 'NF 123', 'Boleto NF 123', 'Comprovante NF 123' para melhor conciliação.")
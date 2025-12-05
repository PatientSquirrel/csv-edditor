import streamlit as st
import pandas as pd
import os
from pathlib import Path
import fitz
from PIL import Image
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

st.set_page_config(page_title="CSV Editor", layout="wide")
CSV_PATH = "/home/copy/projects/gitea-keycloak-sso/data.csv"

# Session State Init
for key, val in {'df': None, 'loaded': False, 'selected_row_idx': None, 'selected_attachment': None, 'attachments_list': []}.items():
    st.session_state.setdefault(key, val)

# Helper Functions
load_csv = lambda p: next((pd.read_csv(p, encoding=e) for e in ['utf-8', 'latin-1'] if not (pd.read_csv(p, encoding=e) is None)), None)

def save_csv(df, p):
    try:
        df.to_csv(p, index=False, encoding='utf-8')
        return True
    except Exception as e:
        st.error(f"Fehler beim Speichern: {e}")
        return False

load_text = lambda p: next((open(p, 'r', encoding=e).read() for e in ['utf-8', 'latin-1'] if os.path.exists(p)), f"Datei nicht gefunden: {p}")
get_val = lambda df, i, c: str(df.loc[i, c]) if c in df.columns and pd.notna(df.loc[i, c]) else ''
valid_path = lambda p: p and p.strip() and p != 'nan'

def render_pdf(path, key):
    pk = f"pdf_page_{key}"
    st.session_state.setdefault(pk, 0)
    doc = fitz.open(path)
    total, curr = len(doc), st.session_state[pk]
    doc.close()
    
    c1, c2, c3 = st.columns([1, 3, 1])
    with c1:
        if st.button("◀", key=f"p_{key}", disabled=curr==0, width="stretch"):
            st.session_state[pk] = max(0, curr-1)
            st.rerun()
    with c2:
        st.markdown(f"<div style='text-align:center;padding:10px'>Seite {curr+1}/{total}</div>", unsafe_allow_html=True)
    with c3:
        if st.button("▶", key=f"n_{key}", disabled=curr>=total-1, width="stretch"):
            st.session_state[pk] = min(total-1, curr+1)
            st.rerun()
    
    doc = fitz.open(path)
    pix = doc[curr].get_pixmap(matrix=fitz.Matrix(2, 2))
    st.image(Image.frombytes("RGB", [pix.width, pix.height], pix.samples), width="stretch")
    doc.close()

def show_attachment(path, key):
    if not os.path.exists(path):
        return st.warning(f"Datei nicht gefunden: {path}")
    ext = Path(path).suffix.lower()
    if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
        st.image(path, width="stretch")
    elif ext == '.pdf':
        render_pdf(path, key)
    elif ext in ['.txt', '.md', '.log', '.json', '.xml']:
        st.text_area("", load_text(path), height=300, disabled=True, label_visibility="collapsed")
    else:
        st.info(f"Dateityp {ext} nicht unterstützt")

def prep_df(df, search):
    if search:
        mask = df.astype(str).apply(lambda x: x.str.contains(search, case=False, na=False)).any(axis=1)
        filt = df[mask].reset_index(drop=True)
        filt.insert(0, '_original_index', df[mask].index)
        return filt
    result = df.copy()
    result.insert(0, '_original_index', df.index)
    return result

def create_grid(df):
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_selection(selection_mode='single', use_checkbox=False, pre_selected_rows=[])
    gb.configure_grid_options(domLayout='normal', onRowClicked=JsCode("function(e){let a=e.api,i=e.rowIndex,n=a.getDisplayedRowAtIndex(i);return n&&n.setSelected(!0),!0}"))
    return AgGrid(df, gridOptions=gb.build(), allow_unsafe_jscode=True, theme='streamlit', height=400, fit_columns_on_grid_load=True, update_on=['selectionChanged'])

def process_selection(resp):
    if resp and 'selected_rows' in resp:
        sel = resp['selected_rows']
        if isinstance(sel, pd.DataFrame) and len(sel) > 0:
            try:
                idx = int(sel.iloc[0]['_original_index'])
                if idx != st.session_state.selected_row_idx:
                    st.session_state.selected_attachment = None
                st.session_state.selected_row_idx = idx
            except Exception as e:
                st.error(f"Fehler: {e}")

# Main
if not st.session_state.loaded:
    if os.path.exists(CSV_PATH):
        st.session_state.df = load_csv(CSV_PATH)
        st.session_state.loaded = True
    else:
        st.error(f"CSV nicht gefunden: {CSV_PATH}")
        st.stop()

st.title("📊 CSV Editor")
df = st.session_state.df

if df is not None:
    search = st.text_input("🔍 Suche", placeholder="Nach beliebigem Text suchen...")
    disp = prep_df(df, search)
    st.write(f"**{len(disp)}** von **{len(df)}** Zeilen")
    
    st.subheader("Datentabelle")
    process_selection(create_grid(disp))
    
    if (idx := st.session_state.selected_row_idx) is not None and idx in df.index:
        st.markdown("---")
        st.subheader(f"📝 Bearbeiten: Zeile {idx+1}")
        if 'ID' in df.columns:
            st.caption(f"ID: {df.loc[idx, 'ID']}")
        
        c1, c2 = st.columns(2)
        with c1:
            bear = st.text_input("Bearbeiter", get_val(df, idx, 'Berabeiter'), key=f"b_{idx}")
        with c2:
            bem = st.text_area("Bemerkung", get_val(df, idx, 'Bemerkung'), key=f"bm_{idx}", height=100)
        
        if st.button("💾 Speichern", type="primary", width="stretch"):
            df.loc[idx, 'Berabeiter'], df.loc[idx, 'Bemerkung'] = bear, bem
            st.session_state.df = df
            if save_csv(df, CSV_PATH):
                st.success("✅ Gespeichert!")
                st.rerun()
        
        st.markdown("---")
        st.subheader("📄 Textdateien")
        c1, c2 = st.columns(2)
        
        for col, name in [(c1, 'Original'), (c2, 'Übersetzung')]:
            with col:
                st.markdown(f"**{name}:**")
                if name in df.columns and valid_path(p := get_val(df, idx, name)):
                    st.text_area(name, load_text(p), height=200, key=f"{name}_{idx}", disabled=True, label_visibility="collapsed")
                else:
                    st.info("Kein Pfad" if name in df.columns else f"Spalte '{name}' fehlt")
        
        st.markdown("---")
        st.subheader("📎 Anhänge")
        
        if 'Anhänge' in df.columns and valid_path(ap := get_val(df, idx, 'Anhänge')):
            files = [f.strip() for f in ap.split(',')]
            st.markdown("**Verfügbare Anhänge:**")
            cols = st.columns(min(len(files), 4))
            
            for i, fp in enumerate(files):
                if fp and os.path.exists(fp):
                    with cols[i % 4]:
                        if st.button(Path(fp).name, key=f"a_{idx}_{i}", width="stretch"):
                            st.session_state.selected_attachment = fp
            
            if (att := st.session_state.selected_attachment):
                st.markdown("---")
                st.subheader(f"📂 Vorschau: {Path(att).name}")
                show_attachment(att, "sel")
        else:
            st.info("Keine Anhänge" if 'Anhänge' in df.columns else "Spalte 'Anhänge' fehlt")
else:
    st.error("Keine Daten geladen")

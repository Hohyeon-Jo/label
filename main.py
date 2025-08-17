import os
import io
import re
import json
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_ID = os.getenv("OPENAI_MODEL") or "gpt-4o-mini"

ALLOWED = ["INT","BIGINT","FLOAT","DECIMAL","BOOLEAN","DATE","DATETIME","TIME","CHAR","VARCHAR","TEXT","JSON","UUID","EMAIL","PHONE"]

try:
    from openai import OpenAI
    client = OpenAI(api_key=API_KEY) if API_KEY else None
except:
    client = None


up = st.file_uploader("파일 선택", type=["txt","csv"])

def read_any(f):
    nm = (getattr(f,"name","") or "").lower()
    if nm.endswith(".txt"):
        try:
            f.seek(0); s = f.read().decode("utf-8","ignore")
        except:
            f.seek(0); s = f.read().decode("cp949","ignore")
        rows = [x.strip() for x in s.splitlines() if (x or "").strip()]
        return pd.DataFrame({"field": rows})
    else:
        df = None
        for enc in ["utf-8","cp949","euc-kr","utf8","latin1"]:
            try:
                f.seek(0)
                df = pd.read_csv(f, encoding=enc)
                break
            except:
                pass
        if df is None:
            st.warning("CSV 읽기 실패")
            raise Exception("csv encoding fail")
        cols = [str(c).lower() for c in df.columns]
        if "field" in cols:
            use = df.columns[cols.index("field")]
        elif "name" in cols:
            use = df.columns[cols.index("name")]
        else:
            use = df.columns[0]
        return pd.DataFrame({"field": df[use].fillna("").astype(str)})

def my_guess(x):
    s = (x or "").strip().lower()
    if s == "":
        return None
    if "email" in s or "e_mail" in s:
        return "EMAIL"
    if ("phone" in s) or ("tel" in s) or ("mobile" in s) or ("contact" in s):
        return "PHONE"
    if s == "id" or s.endswith("_id"):
        if "uuid" in s:
            return "UUID"
        return "INT"
    if re.search(r'(^|_)num($|_)', s) or ("count" in s) or ("qty" in s) or ("quantity" in s) or ("age" in s):
        return "INT"
    if any(k in s for k in ["price","amount","total","balance","rate","ratio","percent","avg","mean","score"]):
        return "DECIMAL"
    if any(k in s for k in ["created_at","updated_at","deleted_at","timestamp"]):
        return "DATETIME"
    if ("date" in s) or ("dob" in s) or ("birth" in s):
        return "DATE"
    if "time" in s:
        return "TIME"
    if any(k in s for k in ["desc","memo","note","comment","content","body","text"]):
        return "TEXT"
    if "name" in s:
        return "VARCHAR"
    return "VARCHAR"

def ask_model(field_name):
    if not client:
        return None
    prom = '타입만. JSON 한 줄: {"type":"VARCHAR"}\n컬럼: ' + str(field_name)
    try:
        r = client.responses.create(
            model=MODEL_ID,
            input=[{"role":"user","content":prom}],
            temperature=0.7
        )
        txt = getattr(r, "output_text", "") or ""
        m = re.search(r"\{.*\}", txt)
        if not m:
            return None
        d = json.loads(m.group(0))
        t = str(d.get("type","")).strip().upper()
        if t not in ALLOWED:
            return None
        return t
    except:
        return None

if up is None:
    st.stop()

try:
    df = read_any(up)
except Exception as e:
    st.error("읽기 실패.. " + str(e))
    st.stop()

st.write("행 개수:", len(df))
st.dataframe(df.head(15), use_container_width=True)


if st.button("시작"):
    res = []
    prog = st.progress(0)
    N = len(df) if len(df)>0 else 1
    for i, rr in df.iterrows():
        col = str(rr["field"]).strip()
        t = my_guess(col)
        if t is None:
            t = ask_model(col)
        if not t:
            t = "VARCHAR"
        if t not in ALLOWED:
            t = "VARCHAR"
        if i < 3:
           pass
        res.append({"field": col, "type": t})
        try:
            prog.progress(int((i+1)/N*100))
        except:
            pass
    out = pd.DataFrame(res)
    st.subheader("결과")
    st.dataframe(out, use_container_width=True)
    buf = io.BytesIO()
    out.to_csv(buf, index=False)
    st.download_button(
        "CSV 다운로드 하기",
        data=buf.getvalue(),
        file_name="db_type_guess.csv",
        mime="text/csv"
    )
    st.success("완료")
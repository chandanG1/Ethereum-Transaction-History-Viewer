import os
import math
import json
import requests
import pandas as pd
import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime

ALCHEMY_API_KEY = st.secrets.get("ALCHEMY_API_KEY", os.getenv("ALCHEMY_API_KEY", ""))
NETWORK = st.secrets.get("NETWORK", os.getenv("NETWORK", "eth-sepolia")).strip()  

if not ALCHEMY_API_KEY:
    st.error("Missing ALCHEMY_API_KEY. Add it in Streamlit Secrets.")
    st.stop()

ALCHEMY_BASE = f"https://{NETWORK}.g.alchemy.com/v2/{ALCHEMY_API_KEY}"

def safe_json(resp: requests.Response):
    """Return resp.json() if JSON, otherwise a dict with error text."""
    try:
        return resp.json()
    except Exception:
        return {"_non_json": True, "status": resp.status_code, "text": resp.text[:500]}

def hex_or_dec_to_int(x):
    if x is None:
        return None
    s = str(x)
    try:
        if s.startswith("0x"):
            return int(s, 16)
        return int(s)
    except Exception:
        return None

def wei_to_eth(x):
    if x is None:
        return None
    try:
        return float(x) / 1e18
    except Exception:
        return None

def get_transactions(address, page_key=None, categories=None):
    cats = categories or ["external", "internal", "erc20", "erc721", "erc1155"]
    payload = {
        "id": 1,
        "jsonrpc": "2.0",
        "method": "alchemy_getAssetTransfers",
        "params": [{
            "fromBlock": "0x0",
            "toBlock": "latest",
            "withMetadata": True,
            "excludeZeroValue": False,
            "maxCount": "0x3e8",
            "category": cats,
            "pageKey": page_key,
            "fromAddress": address,
            "toAddress": address
        }]
    }
    r = requests.post(ALCHEMY_BASE, json=payload, timeout=30)
    return safe_json(r)

def fetch_all(address):
    all_tx = []
    page_key = None
    while True:
        data = get_transactions(address, page_key)
        if "_non_json" in data:
            raise RuntimeError(f"Alchemy returned non-JSON (status {data.get('status')}): {data.get('text')}")
        transfers = (data.get("result") or {}).get("transfers", [])
        all_tx.extend(transfers)
        page_key = (data.get("result") or {}).get("pageKey")
        if not page_key:
            break
    return all_tx

def get_nft_metadata(contract_address, token_id):
    url = f"{ALCHEMY_BASE}/getNFTMetadata"
    params = {"contractAddress": contract_address, "tokenId": token_id}
    try:
        r = requests.get(url, params=params, timeout=12)
        j = safe_json(r)
        if "_non_json" in j:
            return {}
        return j or {}
    except Exception:
        return {}

def normalize_transfers(txs):
    """Normalize raw Alchemy transfers into a friendly table."""
    out = []
    for t in txs:
        category = t.get("category")
        raw = t.get("rawContract") or {}
        meta = t.get("metadata") or {}

        ts_str = meta.get("blockTimestamp") if isinstance(meta, dict) else None
        try:
            ts = pd.to_datetime(ts_str)
        except Exception:
            ts = pd.NaT

        row = {
            "timestamp": ts,
            "category": category,
            "from": t.get("from"),
            "to": t.get("to"),
            "hash": t.get("hash"),
            "blockNum": t.get("blockNum"),
            "contract_address": raw.get("address") or "",
        }

        native_val_int = hex_or_dec_to_int(t.get("value"))
        row["value_eth"] = wei_to_eth(native_val_int) if native_val_int is not None else None

        token_symbol = t.get("asset") or t.get("tokenSymbol")
        token_decimals = t.get("tokenDecimal") or t.get("tokenDecimals")
        token_decimals = hex_or_dec_to_int(token_decimals) if token_decimals is not None else None

        token_raw = t.get("erc20Token", {}).get("rawAmount") if t.get("erc20Token") else None
        if token_raw is None:
            token_raw = t.get("tokenAmount") or t.get("amount") or t.get("value")
        token_raw_int = hex_or_dec_to_int(token_raw)

        token_amount = None
        if token_raw_int is not None:
            d = token_decimals if (isinstance(token_decimals, int) and 0 <= token_decimals <= 36) else None
            if d is None:
                token_amount = token_raw_int / 1e18 if token_raw_int > 10**20 else float(token_raw_int)
            else:
                token_amount = token_raw_int / (10 ** d)

        row["token_symbol"] = token_symbol
        row["token_amount"] = token_amount
        row["token_decimals"] = token_decimals

        token_id = t.get("tokenId") or (t.get("erc721Token") or {}).get("tokenId")
        row["token_id"] = token_id
        row["is_nft"] = category in ("erc721", "erc1155")

        out.append(row)

    df = pd.DataFrame(out)
    if not df.empty:
        df = df.sort_values("timestamp", ascending=False)
    return df

st.set_page_config(page_title="Ethereum Tx Viewer (Sepolia)", page_icon="🔍", layout="wide")
st.title("Ethereum Transaction History Viewer (Sepolia)")
st.caption(f"Network: **{NETWORK}** • Data via Alchemy Transfers API")

st.write("Try a Sepolia address with activity. Example (random test): `0x0000000000000000000000000000000000000000` (replace with a real active Sepolia address).")

address = st.text_input("Enter an Ethereum address (0x...) on Sepolia:", value="", placeholder="0x...")

colA, colB = st.columns([1, 3])
with colA:
    fetch_clicked = st.button("Fetch Transactions")

if fetch_clicked:
    if not address or not address.startswith("0x") or len(address) < 10:
        st.error("Please enter a valid 0x address.")
        st.stop()

    with st.spinner("Fetching transfers from Alchemy..."):
        try:
            txs = fetch_all(address)
        except Exception as e:
            st.error(f"Error fetching data: {e}")
            st.stop()

    df_raw = pd.DataFrame(txs)
    if df_raw.empty:
        st.warning("No transfers found for this address on Sepolia.")
        st.stop()

    df = normalize_transfers(txs)

    eth_df = df[df["category"].isin(["external", "internal"])].copy()

    def safe_lower(x): 
        return x.lower() if isinstance(x, str) else ""
    eth_df["to_l"] = eth_df["to"].apply(safe_lower)
    eth_df["from_l"] = eth_df["from"].apply(safe_lower)

    total_in = eth_df.loc[eth_df["to_l"] == address.lower(), "value_eth"].fillna(0).sum()
    total_out = eth_df.loc[eth_df["from_l"] == address.lower(), "value_eth"].fillna(0).sum()
    net = total_in - total_out

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Received (ETH)", f"{total_in:.6f}")
    m2.metric("Total Sent (ETH)", f"{total_out:.6f}")
    m3.metric("Net (ETH)", f"{net:.6f}")

    flow_series = eth_df.groupby(eth_df["timestamp"].dt.date)["value_eth"].sum(min_count=1).fillna(0)
    if flow_series.sum() != 0 and not flow_series.empty:
        st.subheader("📈 Daily ETH Flow")
        fig, ax = plt.subplots(figsize=(8, 3))
        flow_series.plot(ax=ax)
        ax.set_xlabel("Date")
        ax.set_ylabel("ETH")
        ax.grid(True, linestyle="--", alpha=0.3)
        st.pyplot(fig)
    else:
        st.info("No non-zero native ETH movement detected on this address (Sepolia).")

    tokens_df = df[df["token_symbol"].notna() & df["token_symbol"].astype(str).ne("")].copy()
    if not tokens_df.empty:
        st.subheader("ERC-20 Token Activity (Transfers)")
        token_counts = tokens_df.groupby("token_symbol")["hash"].count().sort_values(ascending=False).head(20)
        st.bar_chart(token_counts)

        st.caption("Note: Amounts are normalized using reported/assumed decimals (fallback heuristic used if decimals missing).")

    nft_df = df[df["is_nft"] & df["token_id"].notna()].copy()
    if not nft_df.empty:
        st.subheader("NFT Gallery (first 24 transfers)")
        nft_subset = nft_df.head(24).copy()
        images = []
        for _, row in nft_subset.iterrows():
            ca = row["contract_address"]
            tid = str(row["token_id"])
            img_url = None
            if ca and tid:
                meta = get_nft_metadata(ca, tid)
                if meta:
                    media = meta.get("media") or []
                    if media and isinstance(media, list):
                        img_url = media[0].get("gateway") or media[0].get("raw")
                    if not img_url:
                        md2 = meta.get("metadata") or {}
                        img_url = md2.get("image") or md2.get("image_url")
            images.append((img_url, ca, tid, row.get("token_symbol","")))

        cols = st.columns(3)
        for i, (img, ca, tid, sym) in enumerate(images):
            with cols[i % 3]:
                if img:
                    st.image(img, use_column_width=True)
                st.caption(f"Contract: `{ca}`\n\nToken ID: `{tid}`")

    st.subheader("Normalized Transactions")
    display_cols = [
        "timestamp", "category", "from", "to",
        "value_eth", "token_symbol", "token_amount",
        "contract_address", "token_id", "hash"
    ]
    safe_df = df[display_cols].copy()
    if "value_eth" in safe_df.columns:
        safe_df["value_eth"] = safe_df["value_eth"].map(lambda x: f"{x:.6f}" if pd.notna(x) else "")
    if "token_amount" in safe_df.columns:
        def fmt_amt(x):
            if pd.isna(x): return ""
            try:
                return f"{float(x):.6f}"
            except Exception:
                return str(x)
        safe_df["token_amount"] = safe_df["token_amount"].map(fmt_amt)

    st.dataframe(safe_df, use_container_width=True)

    export_df = df.copy()
    export_df["timestamp"] = export_df["timestamp"].astype(str)
    csv_bytes = export_df.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV (friendly)", csv_bytes, "transactions_friendly.csv", mime="text/csv")

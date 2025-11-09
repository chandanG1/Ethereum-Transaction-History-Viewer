# Streamlit app.py (full file, simplified basic version)

import streamlit as st
ALCHEMY_API_KEY = st.secrets["ALCHEMY_API_KEY"]
NETWORK = st.secrets.get("NETWORK", "eth-mainnet")

import pandas as pd
import requests
import matplotlib.pyplot as plt
from fpdf import FPDF

ALCHEMY_API_KEY = "UN6bfx9n8Qu36afdw__3Q"
NETWORK = "eth-sepolia"

def get_transactions(address, page_key=None):
    url = f"https://{NETWORK}.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
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
            "category": ["external","internal","erc20","erc721","erc1155"],
            "pageKey": page_key,
            "fromAddress": address,
            "toAddress": address
        }]
    }
    res = requests.post(url, json=payload)
    return res.json()

def fetch_all(address):
    all_tx = []
    page_key = None
    while True:
        data = get_transactions(address, page_key)
        txs = data.get("result", {}).get("transfers", [])
        all_tx.extend(txs)
        page_key = data.get("result", {}).get("pageKey")
        if not page_key:
            break
    return all_tx

st.title("Ethereum Transaction Explorer")

address = st.text_input("Enter Ethereum address")

if st.button("Fetch Data"):
    txs = fetch_all(address)
    df = pd.DataFrame(txs)

    if df.empty:
        st.error("No transactions found")
    else:
        df["timestamp"] = df["metadata"].apply(lambda x: x.get("blockTimestamp") if isinstance(x, dict) else None)
        df["date"] = pd.to_datetime(df["timestamp"]).dt.date

        st.subheader("Transactions")
        st.dataframe(df)

        eth_df = df[df["category"].isin(["external","internal"])]
        eth_df["value_numeric"] = pd.to_numeric(eth_df["value"], errors="coerce").fillna(0)

        total_in = eth_df[eth_df["to"].str.lower()==address.lower()]["value_numeric"].sum()
        total_out = eth_df[eth_df["from"].str.lower()==address.lower()]["value_numeric"].sum()

        st.write(f"Total Received: {total_in} ETH")
        st.write(f"Total Sent: {total_out} ETH")
        st.write(f"Net: {total_in-total_out} ETH")

        flow = eth_df.groupby("date")["value_numeric"].sum()
        if flow.sum() > 0:
            fig, ax = plt.subplots()
            flow.plot(ax=ax)
            st.pyplot(fig)

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", csv, "tx.csv")


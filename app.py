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
    import math, time

    df_raw = pd.DataFrame(txs)

    if df_raw.empty:
        st.error("No transactions found")
    else:
        def get_ts(m):
            if isinstance(m, dict):
                return m.get("blockTimestamp")
            return None

        normalized = []
        for t in txs:
            category = t.get("category")
            raw = t.get("rawContract", {}) or {}
            meta = t.get("metadata") or {}

            tx = {
                "category": category,
                "hash": t.get("hash"),
                "uniqueId": t.get("uniqueId"),
                "blockNum": t.get("blockNum"),
                "timestamp": get_ts(meta),
                "from": t.get("from"),
                "to": t.get("to"),
            }

            value_raw = t.get("value")
            eth_value = 0.0
            try:
                if value_raw is not None and str(value_raw).strip() != "":
                    vr = str(value_raw)
                    if vr.startswith("0x") or "x" in vr:
                        eth_value = int(vr, 16) / 1e18
                    else:
                        eth_value = int(vr) / 1e18
            except Exception:
                eth_value = float("nan")
            tx["value_eth"] = eth_value

            token_symbol = t.get("asset") or t.get("erc20Token", {}).get("symbol") or t.get("tokenSymbol")
            token_raw_amount = None
            token_decimals = None

            if t.get("erc20Token"):
                erc20 = t.get("erc20Token")
                token_raw_amount = erc20.get("rawAmount") or erc20.get("amount") or t.get("value")
                token_decimals = erc20.get("decimals") or erc20.get("tokenDecimals")
     
            if token_raw_amount is None:
                token_raw_amount = t.get("value") or t.get("tokenAmount") or t.get("amount")
            if token_decimals is None:
                token_decimals = t.get("tokenDecimal") or t.get("tokenDecimals")

            try:
                token_decimals = int(token_decimals) if token_decimals is not None else None
            except Exception:
                token_decimals = None

            human_token_amount = None
            if token_raw_amount is not None:
                try:
                    s = str(token_raw_amount)
                    if s.startswith("0x"):
                        ival = int(s, 16)
                    else:
                        ival = int(s)
                    if token_decimals:
                        human_token_amount = ival / (10 ** token_decimals)
                    else:
                        if ival > 10**20:
                            human_token_amount = ival / 1e18
                        else:
                            human_token_amount = ival
                except Exception:
                    human_token_amount = None

            tx["token_symbol"] = token_symbol
            tx["token_amount"] = human_token_amount
            tx["token_decimals"] = token_decimals

            token_id = t.get("tokenId") or (t.get("erc721Token", {}) or {}).get("tokenId")
            tx["token_id"] = token_id
            tx["is_nft"] = category in ("erc721", "erc1155")

            tx["contract_address"] = raw.get("address") or t.get("rawContract", {}).get("address")

            gas_used = None
            try:
                  if isinstance(meta, dict):
                    gas_used = meta.get("gas") or meta.get("gasUsed") or meta.get("effectiveGasPrice")
               
                    if isinstance(gas_used, str) and gas_used.startswith("0x"):
                        gas_used = int(gas_used, 16)
            except Exception:
                gas_used = None
             tx["gas_used"] = gas_used

            tx["nft_image"] = None
            if tx["is_nft"] and tx["contract_address"] and token_id:
                try:
                    nft_api = f"https://{NETWORK}.g.alchemy.com/v2/{ALCHEMY_API_KEY}/getNFTMetadata?contractAddress={tx['contract_address']}&tokenId={token_id}"
                     r = requests.get(nft_api, timeout=8)
                    j = r.json() if r.status_code == 200 else {}
                    media = j.get("media") or []
                    if media and isinstance(media, list):
                         tx["nft_image"] = media[0].get("gateway") or media[0].get("raw") or None
            
                    if not tx["nft_image"]:
                        meta2 = j.get("metadata") or {}
                        tx["nft_image"] = meta2.get("image") or meta2.get("image_url")
                except Exception:
                    tx["nft_image"] = None

            normalized.append(tx)

        df = pd.DataFrame(normalized)

        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.sort_values(by="timestamp", ascending=False)

    
        display_cols = ["timestamp", "category", "from", "to", "value_eth",
                          "token_symbol", "token_amount", "contract_address", "token_id", "is_nft", "hash"]
        st.subheader("Normalized Transactions")
        st.dataframe(df[display_cols].fillna(""))

    
        eth_df = df[df["category"].isin(["external", "internal"])]
        total_in = eth_df[eth_df["to"].str.lower() == address.lower()]["value_eth"].sum()
        total_out = eth_df[eth_df["from"].str.lower() == address.lower()]["value_eth"].sum()
        st.subheader("ETH Summary")
        st.write(f"Total Received: {total_in:.6f} ETH")
        st.write(f"Total Sent: {total_out:.6f} ETH")
        st.write(f"Net: {total_in - total_out:.6f} ETH")

    
        token_counts = df[df["token_symbol"].notna()].groupby("token_symbol")["hash"].count().sort_values(ascending=False)
        if not token_counts.empty:
            st.subheader("Top Tokens by Transfer Count")
            st.bar_chart(token_counts)

   
        nfts = df[df["is_nft"] & df["nft_image"].notna()]
        if not nfts.empty:
            st.subheader("NFT Gallery")
            for _, row in nfts.head(20).iterrows():
                if row["nft_image"]:
                    st.image(row["nft_image"], width=160)
                st.write(f"{row['token_symbol'] or ''} — Contract: {row['contract_address']} — Token ID: {row['token_id']}")
                st.write("---")

   
        export_df = df.copy()
        export_df["timestamp"] = export_df["timestamp"].astype(str)
        csv = export_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV (friendly)", csv, "transactions_friendly.csv")


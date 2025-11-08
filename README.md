# Ethereum Transaction History Viewer (Streamlit + Alchemy + Colab)

This project is a full Ethereum transaction explorer built using:

- **Google Colab (Python backend)**
- **Streamlit (frontend UI)**
- **Alchemy Transfers API**
- **Ngrok (temporary public access)**

## Features
- Fetch full Ethereum transaction history using Alchemy
- Analyse:
  - ETH incoming/outgoing
  - ERC-20 token usage
  - NFT transfers (ERC-721 / ERC-1155)
  - Daily charts
- Export:
  - CSV
  - PDF Report
- Simple and clean Streamlit UI

## How to Run (Colab)
1. Upload `app.py` to your Colab session.
2. Install dependencies:
   ```
   !pip install streamlit pyngrok pandas requests matplotlib fpdf pillow
   ```
3. Add your Alchemy API key:
   ```python
   ALCHEMY_API_KEY = "YOUR_KEY"
   ```
4. Run the Streamlit server:
   ```
   !streamlit run app.py --server.headless true &>/dev/null&
   ```
5. Start ngrok:
   ```python
   from pyngrok import ngrok
   ngrok.set_auth_token("YOUR_NGROK_TOKEN")
   print(ngrok.connect(8501))
   ```

## Deployment for Ethereum.org Submission
You should include:
- This README
- Source code (`app.py`)
- Screenshots of UI
- Project explanation
- Demo video or Streamlit Cloud link

## Ethereum.org Submission Steps
1. Push your project to GitHub.
2. Go to https://github.com/ethereum/ethereum-org-website
3. Click **Fork** → make your copy
4. Create a folder under:
   ```
   src/data/community-projects/
   ```
5. Add your `project.json` file (example included)
6. Create Pull Request:
   - Title: *"Ethereum Transaction History Viewer (Student Project)"*
   - Description: what your project does + GitHub link + demo link


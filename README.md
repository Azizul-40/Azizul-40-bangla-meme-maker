# 😂 বাংলা Meme Maker

ছবি দিলে AI বাংলায় caption লিখে meme বানায়। Phone আর PC/laptop দুই জায়গাতেই browser-এ চলে।

## Live করার ধাপ
1. এই folder-এর সব file একটা নতুন GitHub repo-তে push করো (`app.py` repo-র root-এ থাকতে হবে)।
2. https://share.streamlit.io এ GitHub দিয়ে login করো, **Create app** চাপো।
3. Repo বেছে নাও, Main file path: `app.py`।
4. **Advanced settings > Secrets** এ লেখো:
   `ANTHROPIC_API_KEY = "তোমার key"`
5. Deploy চাপো।

API key পাবে https://console.anthropic.com থেকে। সেখানে monthly spend limit সেট করে রাখো।

## Font
App নিজেই বাংলা font খোঁজে। নিশ্চিত থাকতে `fonts/` folder-এ একটা বাংলা `.ttf`
(যেমন HindSiliguri-Bold.ttf বা NotoSansBengali-Bold.ttf) রেখে দাও।

## Local এ চালাতে
```
pip install -r requirements.txt
mkdir .streamlit   # যদি না থাকে
# .streamlit/secrets.toml এ ANTHROPIC_API_KEY দাও
streamlit run app.py
```

## Phone-এ app-এর মতো
Live link phone browser-এ খুলে "Add to Home Screen" দিলে app icon হয়ে যাবে।

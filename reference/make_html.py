import requests

url = "https://scatch.ssu.ac.kr/%EA%B3%B5%EC%A7%80%EC%82%AC%ED%95%AD/?slug=2025%ED%95%99%EB%85%84%EB%8F%84-2%ED%95%99%EA%B8%B0-%EC%8B%A0%C2%B7%ED%8E%B8%EC%9E%85%EC%83%9D-%ED%95%99%EC%83%9D%EC%A6%9D%EC%8A%A4%EB%A7%88%ED%8A%B8%EC%B9%B4%EB%93%9C-%EC%8B%A0%EC%B2%AD-%EC%95%88&category=%ED%95%99%EC%82%AC"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}
html = requests.get(url, headers=headers).text


with open("reference/fetched.html", "w", encoding="utf-8") as f:
    f.write(html)

import subprocess
from email.header import Header
from email.utils import formatdate

def rfc2047(s):  # 한글 등 비ASCII 헤더 인코딩
    return Header(s, 'utf-8').encode()

email_content = f"""To: tjrals120@gmail.com
From: tjrals120@gmail.com
Subject: {rfc2047(f'[{dept}]{title}')}
MIME-Version: 1.0
Content-Type: text/html; charset=utf-8
Content-Transfer-Encoding: 8bit
Date: {formatdate(localtime=True)}

<html>
  <body>
    <h2>{dept}</h2>
    {date}
    <hr>
    {summary.replace("\\n","<br>")}
    <hr>
    <h5><a href="{url}">{title}</a></h5>
  </body>
</html>
"""

# 파일 없이 표준입력으로 직접 전달(권장)
proc = subprocess.run(
    ["ssmtp", "-v", "-t"],  # 또는 ["msmtp", "-t"]
    input=email_content,
    text=True,
    capture_output=True
)
if proc.returncode != 0:
    # 실패 로그 확인
    # print(proc.stdout, proc.stderr) 등으로 기록
    raise RuntimeError(f"send failed: {proc.stderr}")
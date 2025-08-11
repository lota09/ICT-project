import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from langchain.agents import Tool

def send_email(contents, receiver_email):
    '''LLM의 정리 및 요약 내용과 수신자 메일주소를 받아 이메일을 전송하는 함수'''
    ##################################################
    ### 발신자 메일 주소의 앱 비밀번호(2단계 인증)   ###
    ### - 비밀번호를 환경변수에 저장했다고 가정      ###
    ##################################################
    password = os.getenv('EMAIL_PASSWORD')

    ############################################################
    ### 발신자, 수신자 목록 설정                              ###
    ### - receiver_email(객체)의 address 정보가 있다고 가정   ###
    ############################################################
    sender_email = "abc@gmail.com"
    receiver_email = receiver_email.address
    # cf. 다수의 수신자의 경우: receiver_emails = ["A@gmail.com, B@gmail.com"]
    
    # receiver_email(객체)의 subscription 정보가 있다고 가정
    # 맞춤화된 제목 업데이트
    if receiver_email.subscription == 학사공지:
        title = "[학사공지] 업데이트된 내용을 알려드립니다."
    else:
        title = "[비교과프로그램] 업데이트된 내용을 알려드립니다."
    msg = MIMEMultipart()
    msg['Subject'] = title
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg.attach(MIMEText(contents, "plain"))

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, msg.as_string())

####################################################
### TOOL: send_email(contents, receiver_email)   ###
### - contents: LLM의 정리 및 요약 내용           ###
### - receiver_email: 수신자 메일주소             ###
####################################################
tools = [
    Tool(
        name="send_email",
        func= send_email,
        description="Used to send the summarized and organized content from an LLM via email."
    )
]
contents = None
receiver_email = None
send_email(contents, receiver_email)
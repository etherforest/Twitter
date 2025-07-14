import logging
import random
import re
import threading
import time

import requests
import urllib3
from loguru import logger

from proxy_parser import Proxy

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
DROPMAIL_TOKEN = "YOUR_DROPMAIL_TOKEN"
DROPMAIL_API = f"https://dropmail.me/api/graphql/{DROPMAIL_TOKEN}"
DOMAINS_QUERY = '''query { domains { id name availableVia }}'''
INTRODUCE_SESSION = '''mutation($domainId: ID!) { introduceSession(input: {withAddress: true, domainId: $domainId}) { id expiresAt addresses { address } } }'''
GET_MAILS_QUERY = '''query($id: ID!) { session(id: $id) { mails { id text downloadUrl } } }'''

THREAD_COUNT = 30
USE_SSL_VERIFY = False
PROXY_LIST = []
CODE_LIST = []

EMAIL_OUTPUT = "email.txt"
PROXY_FILE = "proxy.txt"
CODES_FILE = "codes.txt"
REGISTER_URL = "https://auth.privy.io/api/v1/passwordless/init"
VERIFY_URL = "https://auth.privy.io/api/v1/passwordless/authenticate"
INVITE_URL = "https://api.app.wardenprotocol.org/api/users/me"

headers_init = {
    "content-type": "application/json",
    "origin": "https://app.wardenprotocol.org",
    "referer": "https://app.wardenprotocol.org",
    "privy-app-id": "cm7f00k5c02tibel0m4o9tdy1",
    "privy-ca-id": "cd7356e8-799e-4a7b-97ce-b302aeac9145",
    "privy-client": "react-auth:2.13.8",
    "user-agent": "Mozilla/5.0"
}

def load_proxies():
    with open(PROXY_FILE, 'r') as f:
        for line in f:
            PROXY_LIST.append(Proxy.from_str(line.strip()).as_url)


def load_codes():
    with open(CODES_FILE, 'r') as f:
        for line in f:
            CODE_LIST.append(line.strip())



def get_proxy():
    return random.choice(PROXY_LIST) if PROXY_LIST else None


def graphql_request(query, variables=None):
    payload = {"query": query}
    resp = requests.post(DROPMAIL_API, json=payload if not variables else {**payload, "variables": variables})
    resp.raise_for_status()
    data = resp.json()
    if 'errors' in data:
        raise Exception(f"GraphQL errors: {data['errors']}")
    return data['data']


def get_domains():
    data = graphql_request(DOMAINS_QUERY)
    return [d for d in data['domains'] if 'API' in d.get('availableVia', [])]


def create_temp_email(domains):
    dom = random.choice(domains)
    sess = graphql_request(INTRODUCE_SESSION, {"domainId": dom['id']})['introduceSession']
    email = sess['addresses'][0]['address']
    return sess['id'], email


def poll_for_code(session_id, timeout=180, interval=5):
    seen = set()
    start = time.time()
    pattern = re.compile(r"\b(\d{6})\b")
    while time.time() - start < timeout:
        mails = graphql_request(GET_MAILS_QUERY, {"id": session_id})['session']['mails'] or []
        for mail in mails:
            if mail['id'] in seen:
                continue
            seen.add(mail['id'])
            text = mail.get('text') or ''
            match = pattern.search(text)
            if match:
                print(f"验证码：{match.group(1)}")
                return match.group(1)
        time.sleep(interval)
    raise TimeoutError("未能获取验证码")


def send_email_otp(email, proxy):
    resp = requests.post(REGISTER_URL, json={"email": email}, headers=headers_init, proxies={"http": proxy, "https": proxy}, verify=USE_SSL_VERIFY)
    if resp.status_code != 200:
        raise RuntimeError(f"发送验证码失败: {resp.status_code} - {resp.text}")


def verify_code(email, code, proxy):
    payload = {"email": email, "code": code, "mode": "login-or-sign-up"}
    resp = requests.post(VERIFY_URL, json=payload, headers=headers_init, proxies={"http": proxy, "https": proxy}, verify=USE_SSL_VERIFY)
    if resp.status_code != 200:
        raise RuntimeError(f"验证失败: {resp.status_code} - {resp.text}")
    return resp.json().get("token")


def send_invite(token, invite_code, proxy):
    headers = {
        **headers_init,
        "authorization": f"Bearer {token}"
    }
    params = {"referralCode": invite_code}
    resp = requests.get(INVITE_URL, headers=headers, params=params, proxies={"http": proxy, "https": proxy}, verify=USE_SSL_VERIFY)
    if resp.status_code != 201:
        raise RuntimeError(f"邀请失败: {resp.status_code} - {resp.text}")
    return resp.json()


def worker(thread_id, domains, invite_code):
    while True:
        try:
            # https://app.wardenprotocol.org/referral?code=80A69
            proxy = get_proxy()
            time.sleep(1)
            session_id, email = create_temp_email(domains)
            print(f"[Worker-{thread_id}] 使用邮箱：{email}")
            send_email_otp(email, proxy)
            code = poll_for_code(session_id)
            token = verify_code(email, code, proxy)
            send_invite(token, invite_code, proxy)
            print(f"[Worker-{thread_id}] ✅ 成功注册邀请: {email}")
            with open(EMAIL_OUTPUT, 'a') as f:
                f.write(email + "\n")
            time.sleep(2)
        except Exception as e:
            print(f"[Worker-{thread_id}] ❌异常: {e}")
            time.sleep(8)


def main():
    load_proxies()
    load_codes()
    # invite_code = input("请输入你的邀请码：").strip()
    try:
        domains = get_domains()
    except Exception as e:
        print(f"[初始化失败] 获取域名失败: {e}")
        return

    threads = []
    for i in range(len(CODE_LIST)):
        t = threading.Thread(target=worker, args=(i + 1, domains, CODE_LIST[i]), name=f"Worker-{i + 1}")
        t.start()
        threads.append(t)

    for t in threads:
        t.join()


if __name__ == '__main__':
    log_format = (
        "<light-blue>[</light-blue><yellow>{time:HH:mm:ss}</yellow><light-blue>]</light-blue> | "
        "<level>{level: <8}</level> | "
        "<cyan>{file}:{line}</cyan> | "
        "<level>{message}</level>"
    )

    # logging.getLogger("web3").setLevel(logging.WARNING)

    logger.add(
        "logs/app.log",
        rotation="10 MB",
        retention="1 month",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{line} - {message}",
        level="INFO",
    )
    main()
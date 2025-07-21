import asyncio
import random
import re
import time

import requests
import urllib3
from loguru import logger
from primp import AsyncClient

from c import Client, new_client
from common import CommonParser
from proxy_parser import Proxy

# pyarmor gen -O dist -r ./ --exclude ./.venv


# pyinstaller --paths=./dist --hidden-import loguru --hidden-import urllib3 --hidden-import pydantic --hidden-import primp --hidden-import jproperties ./main.py --clean



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
semaphore = None  # 限制并发数的信号量

config = None
client:Client = None

COROUTINES_PER_CODE = 30  # 每个邀请码的协程数量

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

lock = asyncio.Lock()

isRunning = False

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


async def graphql_request(query, variables=None,session:AsyncClient = None):
    payload = {"query": query}
    resp = await session.post(DROPMAIL_API, json=payload if not variables else {**payload, "variables": variables})
    if resp.status_code != 200:
        raise Exception(f"GraphQL request failed with status code: {resp.status_code}")
    data = resp.json()
    if 'errors' in data:
        raise Exception(f"GraphQL errors: {data['errors']}")
    return data['data']


async def get_domains(session:AsyncClient):
    data = await graphql_request(DOMAINS_QUERY,session=session)
    return [d for d in data['domains'] if 'API' in d.get('availableVia', [])]


async def create_temp_email(session:AsyncClient):
    dom = random.choice(await get_domains(session))
    res = await graphql_request(INTRODUCE_SESSION, {"domainId": dom['id']}, session=session)
    sess = res['introduceSession']
    email = sess['addresses'][0]['address']
    return sess['id'], email


async def poll_for_code(name,session_id, timeout=180, interval=5,session:AsyncClient = None):
    seen = set()
    start = time.time()
    pattern = re.compile(r"\b(\d{6})\b")
    while time.time() - start < timeout:
        res = await graphql_request(GET_MAILS_QUERY, {"id": session_id}, session=session)
        mails = res['session']['mails'] or []
        for mail in mails:
            if mail['id'] in seen:
                continue
            seen.add(mail['id'])
            text = mail.get('text') or ''
            match = pattern.search(text)
            if match:
                logger.info(f"[{name}] 验证码：{match.group(1)}")
                return match.group(1)
        await asyncio.sleep(interval)
    raise TimeoutError("未能获取验证码")


def send_email_otp(email, proxy):
    resp = requests.post(REGISTER_URL, json={"email": email}, headers=headers_init, proxies={"http": proxy, "https": proxy}, verify=USE_SSL_VERIFY)
    if resp.status_code != 200:
        raise RuntimeError(f"发送验证码失败: {resp.status_code} - {resp.text}")


async def verify_code(email, code, session:AsyncClient):
    payload = {"email": email, "code": code, "mode": "login-or-sign-up"}
    # resp = requests.post(VERIFY_URL, json=payload, headers=headers_init, proxies={"http": proxy, "https": proxy}, verify=USE_SSL_VERIFY)
    resp = await session.post(VERIFY_URL, json=payload, headers=headers_init)
    if resp.status_code != 200:
        raise RuntimeError(f"验证失败: {resp.status_code} - {resp.text}")
    return resp.json().get("token")


async def send_invite(token, invite_code, session:AsyncClient = None):
    headers = {
        **headers_init,
        "authorization": f"Bearer {token}"
    }
    params = {"referralCode": invite_code}
    # resp = requests.get(INVITE_URL, headers=headers, params=params, proxies={"http": proxy, "https": proxy}, verify=USE_SSL_VERIFY)
    resp = await session.get(INVITE_URL, headers=headers, params=params)
    if resp.status_code != 201:
        raise RuntimeError(f"邀请失败: {resp.status_code} - {resp.text}")
    return resp.json()


async def worker(name, invite_code):
    proxy = get_proxy()

    session = AsyncClient(impersonate="chrome_131", verify=False)
    if proxy:
        session.proxy = proxy
    session.timeout = 120
    global isRunning

    while True:
        if not isRunning:
            logger.warning("something went wrong!!!")
            return
        async with semaphore:  # 限制并发数
            result = False
            for i in range(3):
                try:
                    if await client.update_time():
                        result = True
                        break
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.warning("something went wrong!!!")
            if not result:
                isRunning = False
                logger.warning("something went wrong!!!")
                return
            try:
                # https://app.wardenprotocol.org/referral?code=80A69
                await asyncio.sleep(1)
                session_id, email = await create_temp_email(session)
                logger.info(f"[{name}] 使用邮箱：{email}")
                send_email_otp(email, proxy)
                code = await poll_for_code(name,session_id,session=session)
                token = await verify_code(email, code,session=session)
                await send_invite(token, invite_code, session=session)
                logger.info(f"[{name}] ✅ 成功注册邀请: {email}")

                async with lock:
                    with open(EMAIL_OUTPUT, 'a') as f:
                        f.write(email + "\n")
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"[{name}] ❌异常: {e} ")
                await asyncio.sleep(8)

async def create_worker_group(invite_code):
    """为单个邀请码创建协程组"""
    tasks = []
    logger.info(f"为邀请码 {invite_code} 创建 {COROUTINES_PER_CODE} 个协程...")

    for i in range(COROUTINES_PER_CODE):
        name = f"{invite_code}-worker-{i + 1}"
        task = asyncio.create_task(
            worker(name, invite_code),
            name=name
        )
        tasks.append(task)

        # 创建协程时稍微延迟，避免瞬间压力
        if i > 0 and i % 10 == 0:
            await asyncio.sleep(0.1)

    return tasks
    

async def main():
    global semaphore,config,client,isRunning
    config = CommonParser().parse()
    if not config.activation_code or config.activation_code.strip() == "":
        logger.error("activation_code is empty!!!")
        return
    client = new_client(config.activation_code)
    for i in range(3):
        try:
            if await client.sign_in():
                isRunning = True
                break
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.warning("something went wrong!!!")

    if not isRunning:
        logger.warning("something went wrong!!!")
        return
    load_proxies()
    load_codes()
    # invite_code = input("请输入你的邀请码：").strip()
    total_coroutines = len(CODE_LIST) * COROUTINES_PER_CODE
    min_coroutines = COROUTINES_PER_CODE * 2
    if total_coroutines < min_coroutines:
        total_coroutines = min_coroutines

    # 根据总协程数调整并发控制
    max_concurrent = min(total_coroutines, 300)  # 最多同时300个请求
    semaphore = asyncio.Semaphore(max_concurrent)
    all_tasks = []

    for invite_code in CODE_LIST:
        worker_tasks = await create_worker_group(invite_code)
        all_tasks.extend(worker_tasks)

        # 每个邀请码组创建完成后稍微延迟
        await asyncio.sleep(0.2)
    await asyncio.gather(*all_tasks)
    logger.info("程序已结束！！！")
    # threads = []
    # for i in range(30):
    #     # session = AsyncClient(impersonate="chrome_131", verify=False)
    #     # if proxy:
    #     #     session.proxy = proxy
    #     #
    #     # session.timeout = 120
    #     t = threading.Thread(target=worker, args=(i + 1, domains, "80A69"), name=f"Worker-{i + 1}")
    #     t.start()
    #     threads.append(t)
    #
    # for t in threads:
    #     t.join()


if __name__ == '__main__':
    log_format = (
        "<light-blue>[</light-blue><yellow>{time:HH:mm:ss}</yellow><light-blue>]</light-blue> | "
        "<level>{level: <8}</level> | "
        "<cyan>{file}:{line}</cyan> | "
        "<level>{message}</level>"
    )

    # logging.getLogger("web3").setLevel(logging.WARNING)

    logger.add(
        "logs/app_{time:YYYY-MM-DD}.log",
        rotation="10 MB",
        retention="1 month",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{line} - {message}",
        level="INFO",
    )
    asyncio.new_event_loop().run_until_complete(main())

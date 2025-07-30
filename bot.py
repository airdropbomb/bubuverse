import asyncio
import json
import os
import time
import random
import uuid
import re
from colorama import Fore, init
from pyppeteer import launch
from pyppeteer_stealth import stealth
from mnemonic import Mnemonic
from solders.keypair import Keypair
import base58
import aiofiles
from dotenv import load_dotenv
from cryptography.fernet import Fernet
from capmonster_python import RecaptchaV2Task  # CapMonster for reCAPTCHA v2

init(autoreset=True)

# Load encryption key from .env file
load_dotenv()
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')
if not ENCRYPTION_KEY:
    print(Fore.RED + "[!] Error: ENCRYPTION_KEY not found in .env file. Generating a new key...")
    ENCRYPTION_KEY = Fernet.generate_key().decode()
    with open('.env', 'w') as f:
        f.write(f'ENCRYPTION_KEY={ENCRYPTION_KEY}\n')
    print(Fore.YELLOW + "[!] New encryption key generated and saved to .env file.")
cipher = Fernet(ENCRYPTION_KEY.encode())

# Load CapMonster API key from api.txt
async def load_api_key(file_path='api.txt'):
    try:
        async with aiofiles.open(file_path, mode='r') as f:
            api_key = (await f.read()).strip()
            if not api_key:
                print(Fore.RED + "[!] Error: api.txt is empty. Please add a valid CapMonster API key.")
                return None
            return api_key
    except FileNotFoundError:
        print(Fore.RED + "[!] Error: api.txt not found. Please create api.txt with your CapMonster API key.")
        return None

async def load_file(file_path):
    try:
        async with aiofiles.open(file_path, mode='r') as f:
            lines = [line.strip() for line in await f.readlines()]
            if not lines:
                print(Fore.YELLOW + f"[!] {file_path} is empty. Generating random user agents...")
                generated = [
                    f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.randint(70, 120)}.0.{random.randint(1000, 5000)}.0 Safari/537.36"
                    for _ in range(1000)
                ]
                async with aiofiles.open(file_path, mode='w') as f:
                    await f.write('\n'.join(generated))
                print(Fore.GREEN + f"[+] Generated {len(generated)} user agents and saved to {file_path}")
                return generated
            return lines
    except FileNotFoundError:
        print(Fore.YELLOW + f"[!] {file_path} not found. Generating random user agents...")
        generated = [
            f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.randint(70, 120)}.0.{random.randint(1000, 5000)}.0 Safari/537.36"
            for _ in range(1000)
        ]
        async with aiofiles.open(file_path, mode='w') as f:
            await f.write('\n'.join(generated))
        print(Fore.GREEN + f"[+] Generated {len(generated)} user agents and saved to {file_path}")
        return generated

async def load_proxies(file_path):
    try:
        async with aiofiles.open(file_path, mode='r') as f:
            return [line.strip() for line in await f.readlines() if line.strip()]
    except FileNotFoundError:
        print(Fore.YELLOW + "[!] proxy.txt not found. Running without proxy.")
        return []

def parse_proxy(proxy_string):
    match = re.match(r'^(https?:\/\/)?([^:]+):([^@]+)@([^:]+):(\d+)$', proxy_string)
    if match:
        return {
            'host': match[4],
            'port': int(match[5]),
            'username': match[2],
            'password': match[3]
        }
    parts = proxy_string.split(':')
    if len(parts) == 4:
        return {
            'host': parts[0],
            'port': int(parts[1]),
            'username': parts[2],
            'password': parts[3]
        }
    raise ValueError(f"Invalid proxy format: {proxy_string}")

async def save_wallet_data(file_path, data):
    encrypted_data = []
    for wallet in data:
        wallet_copy = wallet.copy()
        wallet_copy['privateKey'] = cipher.encrypt(wallet_copy['privateKey'].encode()).decode()
        encrypted_data.append(wallet_copy)
    async with aiofiles.open(file_path, mode='w') as f:
        await f.write(json.dumps(encrypted_data, indent=2))

async def load_wallet_data(file_path):
    try:
        async with aiofiles.open(file_path, mode='r') as f:
            content = await f.read()
            data = json.loads(content) if content else []
            for wallet in data:
                wallet['privateKey'] = cipher.decrypt(wallet['privateKey'].encode()).decode()
            return data
    except FileNotFoundError:
        return []

async def solve_captcha(capmonster_client, website_url, website_key):
    try:
        task = RecaptchaV2Task(capmonster_client)
        task_id = task.create_task(website_url=website_url, website_key=website_key)
        result = task.join_task_result(task_id)
        return result.get("gRecaptchaResponse")
    except Exception as e:
        print(Fore.RED + f"[!] Error solving CAPTCHA: {str(e)}")
        return None

async def create_wallets(user_agents, wallet_data):
    proxies = await load_proxies('proxy.txt')
    api_key = await load_api_key('api.txt')
    if not api_key:
        print(Fore.RED + "[!] Cannot proceed without a valid CapMonster API key.")
        return
    capmonster_client = CapMonsterClient(api_key=api_key)

    if not user_agents:
        print(Fore.RED + "[!] Error: No user agents found in ua.txt. Please populate ua.txt with valid user agent strings.")
        return
    if not proxies:
        print(Fore.YELLOW + "[!] No proxies found. Running without proxy.")
    elif len(proxies) < count:
        print(Fore.YELLOW + f"[!] Warning: Only {len(proxies)} proxies available for {count} wallets. Some wallets may reuse proxies.")

    referrer_address = input(Fore.YELLOW + 'Enter referrerAddress: ')
    count = int(input(Fore.YELLOW + 'Enter number of wallets to create: '))

    for i in range(count):
        print(Fore.CYAN + f'\n[{i + 1}/{count}] === CREATING NEW WALLET ===')

        user_agent = random.choice(user_agents)
        device_id = str(uuid.uuid4()).replace('-', '')
        proxy = parse_proxy(proxies[i % len(proxies)]) if proxies else None

        mnemo = Mnemonic("english")
        mnemonic = mnemo.generate(strength=128)
        seed = mnemo.to_seed(mnemonic)
        keypair = Keypair.from_seed(seed[:32])
        public_key = str(keypair.pubkey())
        private_key = base58.b58encode(keypair.secret())

        print(Fore.CYAN + f'🌐 Creating wallet: {public_key}')
        print(Fore.CYAN + f'↳ Device ID: {device_id}')
        if proxy:
            print(Fore.CYAN + f'↳ Proxy: {proxy["host"]}:{proxy["port"]}')

        browser = None
        try:
            browser_args = [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-blink-features=AutomationControlled',
                '--no-first-run',
                '--disable-infobars'
            ]
            if proxy:
                browser_args.append(f'--proxy-server={proxy["host"]}:{proxy["port"]}')
            browser = await launch(
                headless=True,
                args=browser_args
            )
            page = await browser.newPage()
            if proxy and proxy.get('username') and proxy.get('password'):
                await page.authenticate({
                    'username': proxy['username'],
                    'password': proxy['password']
                })
            await page.setViewport({'width': 1024, 'height': 768})
            await page.setUserAgent(user_agent)
            await stealth(page)  # Apply stealth mode

            # Additional stealth settings
            await page.evaluateOnNewDocument('''() => {
                Object.defineProperty(navigator, 'webdriver', { get: () => false });
                window.navigator.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            }''')

            target_url = 'https://bubuverse.fun/space'
            print(Fore.YELLOW + f"[DEBUG] Navigating to {target_url}")
            await page.goto(target_url, {'waitUntil': 'networkidle2', 'timeout': 60000})

            await asyncio.sleep(30)  # Increased wait time for CAPTCHA loading

            page_title = await page.title()
            current_url = page.url
            print(Fore.YELLOW + f"[DEBUG] Page title: {page_title}")
            print(Fore.YELLOW + f"[DEBUG] Current URL: {current_url}")

            if 'bubuverse.fun' not in current_url:
                raise Exception(f'Redirect: {current_url}')

            if 'error' in page_title.lower() or 'blocked' in page_title.lower() or 'checkpoint' in page_title.lower():
                print(Fore.YELLOW + "[!] Detected Vercel Security Checkpoint. Attempting to solve CAPTCHA...")

                # Get site key for reCAPTCHA
                website_key = await page.evaluate('''() => {
                    const element = document.querySelector('[data-sitekey]');
                    return element ? element.getAttribute('data-sitekey') : null;
                }''')
                if not website_key:
                    raise Exception("Could not find reCAPTCHA site key!")

                print(Fore.YELLOW + f"[DEBUG] Found reCAPTCHA site key: {website_key}")

                # Solve CAPTCHA using CapMonster
                captcha_solution = await solve_captcha(capmonster_client, target_url, website_key)
                if not captcha_solution:
                    raise Exception("Failed to solve CAPTCHA!")

                print(Fore.GREEN + f"[DEBUG] CAPTCHA solved: {captcha_solution}")

                # Inject CAPTCHA solution
                await page.evaluate(f'''(solution) => {{
                    document.getElementById("g-recaptcha-response").innerHTML = "{captcha_solution}";
                }}''', captcha_solution)

                # Submit CAPTCHA form if required
                await page.evaluate('''() => {
                    const submitButton = document.querySelector('button[type="submit"]') || document.querySelector('#recaptcha-demo-submit');
                    if (submitButton) submitButton.click();
                }''')

                await asyncio.sleep(5)  # Wait for page to process CAPTCHA

                # Re-check page title and URL
                page_title = await page.title()
                current_url = page.url
                print(Fore.YELLOW + f"[DEBUG] Post-CAPTCHA Page title: {page_title}")
                print(Fore.YELLOW + f"[DEBUG] Post-CAPTCHA Current URL: {current_url}")

            cookies = await page.cookies()
            print(Fore.YELLOW + f"[DEBUG] Cookies: {cookies}")
            vcrcs_cookie = next((c for c in cookies if c['name'] == '_vcrcs'), None)

            if not vcrcs_cookie:
                raise Exception("Could not find _vcrcs cookie!")

            print(Fore.GREEN + f"[DEBUG] Found _vcrcs cookie: {vcrcs_cookie['value']}")

            max_retries = 3
            attempt = 0
            response = None

            while attempt < max_retries:
                try:
                    response = await page.evaluate('''
                        async ({ publicKey, referrerAddress, deviceId, cookieValue }) => {
                            const res = await fetch('https://bubuverse.fun/api/users', {
                                method: 'POST',
                                headers: {
                                    'accept': '*/*',
                                    'accept-language': 'vi-VN,vi;q=0.9',
                                    'content-type': 'application/json',
                                    'user-agent': navigator.userAgent,
                                    'referer': location.href,
                                    'origin': 'https://bubuverse.fun',
                                    'cookie': `_vcrcs=${cookieValue}`
                                },
                                body: JSON.stringify({
                                    walletAddress: publicKey,
                                    referrerAddress,
                                    deviceId
                                })
                            });
                            const responseText = await res.text();
                            let json;
                            try {
                                json = JSON.parse(responseText);
                            } catch (e) {
                                json = { error: 'Invalid JSON response', raw: responseText.substring(0, 200) };
                            }
                            return { status: res.status, ok: res.ok, body: json };
                        }
                    ''', {'publicKey': public_key, 'referrerAddress': referrer_address, 'deviceId': device_id, 'cookieValue': vcrcs_cookie['value']})

                    if response['ok']:
                        break
                    attempt += 1
                    print(Fore.YELLOW + f'Retrying request ({attempt}/{max_retries})...')
                    await asyncio.sleep(2)
                except Exception as err:
                    attempt += 1
                    if attempt == max_retries:
                        raise err
                    print(Fore.YELLOW + f'Retrying due to error: {str(err)}')
                    await asyncio.sleep(2)

            if response['ok']:
                wallet = {
                    'mnemonic': mnemonic,
                    'privateKey': private_key.decode(),
                    'publicKey': public_key,
                    'deviceId': device_id,
                    'userAgent': user_agent
                }
                wallet_data.append(wallet)
                await save_wallet_data('wallet_sol.json', wallet_data)
                print(Fore.GREEN + f'[+] Success! Wallet: {public_key}')
            else:
                print(Fore.RED + f'[!] Server error: {response["status"]}')
                print(Fore.LIGHTBLACK_EX + f'Response: {json.dumps(response["body"], indent=2)}')

            await browser.close()
        except Exception as err:
            print(Fore.RED + f'[!] Error creating wallet: {str(err)}')
            if browser:
                await browser.close()

        delay_time = random.uniform(5, 12)
        print(Fore.LIGHTBLACK_EX + f'⏳ Waiting {round(delay_time, 1)}s...')
        await asyncio.sleep(delay_time)

    print(Fore.GREEN + '\n✅ Done. Wallets saved to wallet_sol.json')
    print(Fore.CYAN + f'📊 Total wallets created: {len(wallet_data)}')

async def main():
    user_agents = await load_file('ua.txt')
    wallet_data = await load_wallet_data('wallet_sol.json')
    print(Fore.CYAN + '\n=== BUBUVERSE AUTOMATION TOOL ===')
    print(f'{Fore.GREEN}Loaded {Fore.WHITE}{len(user_agents)} {Fore.GREEN}user agents\n')

    while True:
        print(Fore.CYAN + '\nMenu:')
        print(Fore.GREEN + '1. Create Wallets')
        print(Fore.GREEN + '2. Exit')
        choice = input(Fore.YELLOW + 'Select an option (1-2): ')

        if choice == '1':
            await create_wallets(user_agents, wallet_data)
        elif choice == '2':
            print(Fore.GREEN + 'Exiting... Saving data...')
            await save_wallet_data('wallet_sol.json', wallet_data)
            print(Fore.GREEN + 'Data saved. Goodbye!')
            return
        else:
            print(Fore.RED + 'Invalid option! Please select 1-2.')

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except IndexError as e:
        print(Fore.RED + f'[!] Error: {str(e)}. Please ensure ua.txt contains valid user agent strings.')
    except KeyboardInterrupt:
        print(f'\n\n{Fore.YELLOW}Saving data...')
        asyncio.run(save_wallet_data('wallet_sol.json', wallet_data))
        print(f'{Fore.GREEN}Data saved')
        exit(0)
    except Exception as e:
        print(Fore.RED + f'[!] Fatal error: {str(e)}')
        exit(1)

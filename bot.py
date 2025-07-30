import asyncio
import json
import os
import time
import random
import uuid
from colorama import Fore, init
from pyppeteer import launch
from mnemonic import Mnemonic  # Replaced bip39 with mnemonic
from pyppeteer_stealth import stealth
from solders.keypair import Keypair
import base58
import aiofiles

init(autoreset=True)

# Utility functions
async def load_file(file_path):
    try:
        async with aiofiles.open(file_path, mode='r') as f:
            return [line.strip() for line in await f.readlines()]
    except FileNotFoundError:
        return []

async def load_wallet_data(file_path):
    try:
        async with aiofiles.open(file_path, mode='r') as f:
            content = await f.read()
            return json.loads(content) if content else []
    except FileNotFoundError:
        return []

async def save_wallet_data(file_path, data):
    async with aiofiles.open(file_path, mode='w') as f:
        await f.write(json.dumps(data, indent=2))

def sign_message(message, private_key):
    from solders.signature import Signature
    keypair = Keypair.from_bytes(base58.b58decode(private_key))  # Use base58
    return str(keypair.sign_message(message.encode()))

def get_nft_info(template_id):
    rarity_map = {
        'labubu-00000-1': {'name': 'Blooming Spirit', 'rarity': 'NFT 10x', 'color': Fore.GREEN},
        'labubu-00000-2': {'name': 'Wise Spirit', 'rarity': 'NFT 10x', 'color': Fore.GREEN},
        'labubu-00000-3': {'name': 'Guardian Spirit', 'rarity': 'NFT 10x', 'color': Fore.GREEN},
        'labubu-00000-4': {'name': 'Midnight Spirit', 'rarity': 'NFT 100x', 'color': Fore.YELLOW},
        'labubu-00000-5': {'name': 'Starlight Angel', 'rarity': 'NFT 1000x', 'color': Fore.MAGENTA}
    }
    return rarity_map.get(template_id, {'name': 'Unknown', 'rarity': 'Unknown', 'color': Fore.LIGHTBLACK_EX})

async def get_browser_session(user_agent):
    browser = None
    try:
        browser = await launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        page = await browser.newPage()
        await page.setViewport({'width': 1024, 'height': 768})
        await page.setUserAgent(user_agent)
        await stealth(page)  # Apply stealth to avoid bot detection

        target_url = 'https://bubuverse.fun/space'
        await page.goto(target_url, {'waitUntil': 'networkidle2', 'timeout': 60000})

        await asyncio.sleep(15)

        page_title = await page.title()
        current_url = page.url

        if 'bubuverse.fun' not in current_url:
            raise Exception(f'Redirect: {current_url}')

        if 'error' in page_title.lower() or 'blocked' in page_title.lower():
            raise Exception(f'Error page: {page_title}')

        cookies = await page.cookies()
        cookie_string = '; '.join(f"{cookie['name']}={cookie['value']}" for cookie in cookies)
        vcrcs_cookie = next((cookie for cookie in cookies if cookie['name'] == '_vcrcs'), None)

        if not vcrcs_cookie:
            raise Exception('Could not find _vcrcs cookie')

        return {
            'vcrcs_cookie': vcrcs_cookie['value'],
            'all_cookies': cookie_string,
            'cookie_created_at': time.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
            'cookie_expires_at': time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime(time.time() + 3600)),
            'user_agent': user_agent,
            'page': page,
            'browser': browser
        }
    except Exception as e:
        if browser:
            await browser.close()
        raise Exception(f'Failed to get browser session: {str(e)}')

async def create_wallets(user_agents, wallet_data):
    referrer_address = input(Fore.YELLOW + 'Enter referrerAddress: ')
    count = int(input(Fore.YELLOW + 'Enter number of wallets to create: '))

    for i in range(count):
        print(Fore.CYAN + f'\n[{i + 1}/{count}] === CREATING NEW WALLET ===')

        user_agent = random.choice(user_agents)
        device_id = str(uuid.uuid4()).replace('-', '')

        # Use mnemonic package to generate mnemonic and seed
        mnemo = Mnemonic("english")
        mnemonic = mnemo.generate(strength=128)  # Generate 12-word mnemonic (128-bit)
        seed = mnemo.to_seed(mnemonic)  # Convert mnemonic to seed

        # Derive Solana keypair from seed
        keypair = Keypair.from_seed(seed[:32])  # Use first 32 bytes of seed
        public_key = str(keypair.pubkey())
        private_key = base58.b58encode(keypair.secret())

        print(f'🌐 Creating wallet: {public_key}')
        print(f'↳ Device ID: {device_id}')

        browser = None
        try:
            browser = await launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            page = await browser.newPage()
            await page.setViewport({'width': 1024, 'height': 768})
            await page.setUserAgent(user_agent)

            target_url = 'https://bubuverse.fun/space'
            await page.goto(target_url, {'waitUntil': 'networkidle2', 'timeout': 60000})

            await asyncio.sleep(20)

            cookies = await page.cookies()
            vcrcs_cookie = next((c for c in cookies if c['name'] == '_vcrcs'), None)

            if not vcrcs_cookie:
                raise Exception("Could not find _vcrcs cookie!")

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
                    'privateKey': private_key,
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
    
async def get_boxes_with_puppeteer(page, wallet_address):
    try:
        timestamp = int(time.time() * 1000)
        api_url = f'https://bubuverse.fun/api/users/{wallet_address}/blind-boxes?status=unopened&_t={timestamp}'

        response = await page.evaluate('''
            async (url) => {
                const response = await fetch(url, {
                    method: 'GET',
                    headers: {
                        'accept': '*/*',
                        'referer': 'https://bubuverse.fun/space'
                    },
                    mode: 'cors',
                    credentials: 'include'
                });
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                return await response.json();
            }
        ''', api_url)

        return response.get('data', [])
    except Exception as e:
        raise Exception(f'Failed to get boxes: {str(e)}')

async def open_box_with_puppeteer(page, wallet_address, private_key, box_id):
    try:
        timestamp = int(time.time() * 1000)
        message = f'Open blind box {box_id} at {timestamp}'
        signature = sign_message(message, private_key)

        body = {
            'box_id': box_id,
            'signature': signature,
            'message': message
        }

        api_url = f'https://bubuverse.fun/api/users/{wallet_address}/blind-boxes/open'

        max_retries = 3
        attempt = 0
        response = None

        while attempt < max_retries:
            try:
                response = await page.evaluate('''
                    async (url, requestBody) => {
                        const response = await fetch(url, {
                            method: 'POST',
                            headers: {
                                'accept': '*/*',
                                'content-type': 'application/json',
                                'referer': 'https://bubuverse.fun/space'
                            },
                            body: JSON.stringify(requestBody),
                            mode: 'cors',
                            credentials: 'include'
                        });
                        if (!response.ok) {
                            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                        }
                        return await response.json();
                    }
                ''', api_url, body)

                break
            except Exception as err:
                attempt += 1
                if attempt == max_retries:
                    raise err
                print(Fore.YELLOW + f'Retrying open box ({attempt}/{max_retries})...')
                await asyncio.sleep(2)

        return response
    except Exception as e:
        raise Exception(f'Failed to open box: {str(e)}')

async def open_boxes(user_agents, wallet_data, open_data):
    for i, wallet in enumerate(wallet_data):
        if 'deviceId' not in wallet:
            wallet['deviceId'] = str(uuid.uuid4()).replace('-', '')
        if 'userAgent' not in wallet:
            wallet['userAgent'] = random.choice(user_agents)

        if wallet['publicKey'] in open_data and len(open_data[wallet['publicKey']]) > 0:
            nft_info = get_nft_info(open_data[wallet['publicKey']][0])
            print(f'\n[{i + 1}/{len(wallet_data)}] {Fore.CYAN}{wallet["publicKey"][:8]}...')
            print(f'{Fore.LIGHTBLACK_EX}Skipping - already has {nft_info["color"]}{nft_info["rarity"]}')
            await asyncio.sleep(1)
            continue

        print(f'\n[{i + 1}/{len(wallet_data)}] {Fore.CYAN}{wallet["publicKey"][:8]}...')

        session_data = None
        try:
            print(f'{Fore.YELLOW}Fetching cookies...')
            session_data = await get_browser_session(wallet['userAgent'])
            print(f'{Fore.GREEN}Cookies OK')

            wallet['vcrcsCookie'] = session_data['vcrcs_cookie']
            wallet['allCookies'] = session_data['all_cookies']
            wallet['cookieCreatedAt'] = session_data['cookie_created_at']
            wallet['cookieExpiresAt'] = session_data['cookie_expires_at']

            await save_wallet_data('wallet_sol.json', wallet_data)
        except Exception as e:
            print(f'{Fore.RED}Cookie error: {str(e)}')
            if session_data and session_data['browser']:
                await session_data['browser'].close()
            continue

        try:
            print(f'{Fore.YELLOW}Checking boxes...')
            boxes = await get_boxes_with_puppeteer(session_data['page'], wallet['publicKey'])

            if not boxes:
                print(f'{Fore.LIGHTBLACK_EX}No boxes available')
                await session_data['browser'].close()
                continue

            print(f'{Fore.GREEN}Found {Fore.WHITE}{len(boxes)} {Fore.GREEN}boxes')

            if wallet['publicKey'] not in open_data:
                open_data[wallet['publicKey']] = []

            success_count = 0
            fail_count = 0

            for j, box in enumerate(boxes):
                box_id = box['id']
                try:
                    print(f'{Fore.YELLOW}Opening box {Fore.WHITE}{j + 1}/{Fore.WHITE}{len(boxes)}...')
                    result = await open_box_with_puppeteer(session_data['page'], wallet['publicKey'], wallet['privateKey'], box_id)
                    template_id = result['template_id']

                    open_data[wallet['publicKey']].append(template_id)
                    nft_info = get_nft_info(template_id)
                    print(nft_info['color'] + f'  → {nft_info["rarity"]} - {nft_info["name"]}')

                    success_count += 1
                    if j < len(boxes) - 1:
                        await asyncio.sleep(2)
                except Exception as e:
                    print(f'  → {Fore.RED}Error: {str(e)}')
                    fail_count += 1
                    if j < len(boxes) - 1:
                        await asyncio.sleep(2)

            print(f'{Fore.GREEN}Completed: {Fore.WHITE}{success_count} {Fore.GREEN}OK, {Fore.WHITE}{fail_count} {Fore.RED}failed')
            await save_wallet_data('open.json', open_data)
            await session_data['browser'].close()
        except Exception as e:
            print(f'{Fore.RED}Processing error: {str(e)}')
            if session_data and session_data['browser']:
                await session_data['browser'].close()

        if i < len(wallet_data) - 1:
            print(f'{Fore.LIGHTBLACK_EX}Waiting 3s...')
            await asyncio.sleep(3)

    show_box_stats(open_data)

async def stake_nfts(page, wallet_address, private_key):
    try:
        timestamp = int(time.time() * 1000)
        message = f'Stake NFTs at {timestamp}'
        signature = sign_message(message, private_key)

        body = {
            'signature': signature,
            'message': message
        }

        api_url = f'https://bubuverse.fun/api/users/{wallet_address}/nfts/stake'

        max_retries = 3
        attempt = 0
        response = None

        while attempt < max_retries:
            try:
                response = await page.evaluate('''
                    async (url, requestBody) => {
                        const response = await fetch(url, {
                            method: 'POST',
                            headers: {
                                'accept': '*/*',
                                'content-type': 'application/json'
                            },
                            body: JSON.stringify(requestBody),
                            mode: 'cors',
                            credentials: 'include'
                        });
                        if (!response.ok) {
                            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                        }
                        return await response.json();
                    }
                ''', api_url, body)

                break
            except Exception as err:
                attempt += 1
                if attempt == max_retries:
                    raise err
                print(Fore.YELLOW + f'Retrying stake ({attempt}/{max_retries})...')
                await asyncio.sleep(2)

        return response
    except Exception as e:
        raise Exception(f'Failed to stake NFTs: {str(e)}')

async def stake_wallets(user_agents, wallet_data, open_data):
    for i, wallet in enumerate(wallet_data):
        if 'deviceId' not in wallet:
            wallet['deviceId'] = str(uuid.uuid4()).replace('-', '')
        if 'userAgent' not in wallet:
            wallet['userAgent'] = random.choice(user_agents)

        if wallet['publicKey'] in open_data and any(isinstance(nft, dict) and nft.get('staked') for nft in open_data[wallet['publicKey']]):
            print(f'\n[{i + 1}/{len(wallet_data)}] {Fore.CYAN}{wallet["publicKey"][:8]}...')
            print(f'{Fore.LIGHTBLACK_EX}Skipping - already staked')
            await asyncio.sleep(1)
            continue

        if wallet['publicKey'] not in open_data or not open_data[wallet['publicKey']]:
            print(f'\n[{i + 1}/{len(wallet_data)}] {Fore.CYAN}{wallet["publicKey"][:8]}...')
            print(f'{Fore.LIGHTBLACK_EX}Skipping - no NFTs')
            await asyncio.sleep(1)
            continue

        print(f'\n[{i + 1}/{len(wallet_data)}] {Fore.CYAN}{wallet["publicKey"][:8]}...')

        session_data = None
        try:
            print(f'{Fore.YELLOW}Fetching cookies...')
            session_data = await get_browser_session(wallet['userAgent'])
            print(f'{Fore.GREEN}Cookies OK')
        except Exception as e:
            print(f'{Fore.RED}Cookie error: {str(e)}')
            if session_data and session_data['browser']:
                await session_data['browser'].close()
            continue

        try:
            print(f'{Fore.YELLOW}Staking NFTs...')
            stake_result = await stake_nfts(session_data['page'], wallet['publicKey'], wallet['privateKey'])

            if stake_result.get('success'):
                total_nfts = stake_result['data']['total_nfts']
                success_count = stake_result['data']['success_count']
                failed_count = stake_result['data']['failed_count']
                print(f'{Fore.GREEN}Stake successful: {Fore.WHITE}{success_count}/{Fore.WHITE}{total_nfts} {Fore.GREEN}NFTs')

                if failed_count > 0:
                    print(f'{Fore.RED}Error: {Fore.WHITE}{failed_count} {Fore.RED}NFTs failed')
                    if stake_result['data'].get('error_messages'):
                        for msg in stake_result['data']['error_messages']:
                            print(f'  → {Fore.RED}{msg}')

                if wallet['publicKey'] not in open_data:
                    open_data[wallet['publicKey']] = []

                open_data[wallet['publicKey']] = [
                    {
                        'templateId': nft if isinstance(nft, str) else nft['templateId'],
                        'staked': True,
                        'stakedAt': time.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
                        'stakeResult': {
                            'total_nfts': total_nfts,
                            'success_count': success_count,
                            'failed_count': failed_count,
                            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S.000Z')
                        }
                    } for nft in open_data[wallet['publicKey']]
                ]

                await save_wallet_data('open.json', open_data)
            else:
                print(f'{Fore.RED}Stake failed')

            await session_data['browser'].close()
        except Exception as e:
            print(f'{Fore.RED}Stake error: {str(e)}')
            if session_data and session_data['browser']:
                await session_data['browser'].close()

        if i < len(wallet_data) - 1:
            print(f'{Fore.LIGHTBLACK_EX}Waiting 3s...')
            await asyncio.sleep(3)

    show_stake_stats(len(wallet_data), open_data)

def show_box_stats(open_data):
    print(f'\n{Fore.CYAN}=== Box Opening Statistics ===')
    if not open_data:
        print(f'{Fore.LIGHTBLACK_EX}No data available')
        return

    total_boxes = 0
    rarity_count = {'10x': 0, '100x': 0, '1000x': 0}

    for templates in open_data.values():
        for template in templates:
            total_boxes += 1
            nft_info = get_nft_info(template if isinstance(template, str) else template['templateId'])
            if '10x' in nft_info['rarity']:
                rarity_count['10x'] += 1
            elif '100x' in nft_info['rarity']:
                rarity_count['100x'] += 1
            elif '1000x' in nft_info['rarity']:
                rarity_count['1000x'] += 1

    print(f'\n{Fore.CYAN}Summary:')
    print(f'{Fore.GREEN}NFT 10x: {Fore.WHITE}{rarity_count["10x"]}')
    print(f'{Fore.YELLOW}NFT 100x: {Fore.WHITE}{rarity_count["100x"]}')
    print(f'{Fore.MAGENTA}NFT 1000x: {Fore.WHITE}{rarity_count["1000x"]}')
    print(f'{Fore.BLUE}Total boxes: {Fore.WHITE}{total_boxes}')

def show_stake_stats(total_wallets, open_data):
    print(f'\n{Fore.CYAN}=== Staking Statistics ===')
    if not open_data:
        print(f'{Fore.LIGHTBLACK_EX}No data available')
        return

    wallets_with_staked_nfts = 0
    total_nfts = 0
    total_staked_nfts = 0

    for nfts in open_data.values():
        wallet_staked_count = 0
        for nft in nfts:
            total_nfts += 1
            if isinstance(nft, dict) and nft.get('staked'):
                wallet_staked_count += 1
                total_staked_nfts += 1
        if wallet_staked_count > 0:
            wallets_with_staked_nfts += 1

    print(f'\n{Fore.CYAN}Summary:')
    print(f'{Fore.GREEN}Wallets with staked NFTs: {Fore.WHITE}{wallets_with_staked_nfts}/{Fore.WHITE}{total_wallets}')
    print(f'{Fore.GREEN}NFTs staked: {Fore.WHITE}{total_staked_nfts}/{Fore.WHITE}{total_nfts}')

async def main():
    user_agents = await load_file('ua.txt')
    wallet_data = await load_wallet_data('wallet_sol.json')
    open_data = await load_wallet_data('open.json')

    print(Fore.CYAN + '\n=== BUBUVERSE AUTOMATION TOOL ===')
    print(f'{Fore.GREEN}Loaded {Fore.WHITE}{len(user_agents)} {Fore.GREEN}user agents\n')

    while True:
        print(Fore.CYAN + '\nMenu:')
        print(Fore.GREEN + '1. Create Wallets')
        print(Fore.GREEN + '2. Open Blind Boxes')
        print(Fore.GREEN + '3. Stake NFTs')
        print(Fore.GREEN + '4. Show Box Statistics')
        print(Fore.GREEN + '5. Show Stake Statistics')
        print(Fore.GREEN + '6. Exit')

        choice = input(Fore.YELLOW + 'Select an option (1-6): ')

        if choice == '1':
            await create_wallets(user_agents, wallet_data)
        elif choice == '2':
            if not wallet_data:
                print(Fore.RED + 'No wallets found in wallet_sol.json! Please create wallets first.')
                continue
            await open_boxes(user_agents, wallet_data, open_data)
        elif choice == '3':
            if not wallet_data:
                print(Fore.RED + 'No wallets found in wallet_sol.json! Please create wallets first.')
                continue
            if not open_data:
                print(Fore.RED + 'No NFTs found in open.json! Please open boxes first.')
                continue
            await stake_wallets(user_agents, wallet_data, open_data)
        elif choice == '4':
            show_box_stats(open_data)
        elif choice == '5':
            show_stake_stats(len(wallet_data), open_data)
        elif choice == '6':
            print(Fore.GREEN + 'Exiting... Saving data...')
            await save_wallet_data('wallet_sol.json', wallet_data)
            await save_wallet_data('open.json', open_data)
            print(Fore.GREEN + 'Data saved. Goodbye!')
            return
        else:
            print(Fore.RED + 'Invalid option! Please select 1-6.')

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f'\n\n{Fore.YELLOW}Saving data...')
        asyncio.run(save_wallet_data('wallet_sol.json', wallet_data))
        asyncio.run(save_wallet_data('open.json', open_data))
        print(f'{Fore.GREEN}Data saved')
        exit(0)
    except Exception as e:
        print(Fore.RED + f'[!] Fatal error: {str(e)}')
        exit(1)

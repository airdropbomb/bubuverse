const fs = require('fs');
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const { v4: uuidv4 } = require('uuid');
const readline = require('readline-sync');
const colors = require('colors');
const bip39 = require('bip39');
const ed25519 = require('ed25519-hd-key');
const bs58 = require('bs58');
const nacl = require('tweetnacl');
const { Keypair } = require('@solana/web3.js');

puppeteer.use(StealthPlugin());

const proxies = fs.readFileSync('proxy.txt', 'utf-8').split('\n').filter(Boolean);
let userAgents = [];
if (!fs.existsSync('ua.txt') || fs.readFileSync('ua.txt', 'utf-8').trim() === '') {
  const generated = [];
  for (let i = 0; i < 1000; i++) {
    const ver = Math.floor(Math.random() * 50) + 70;
    const ua = `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${ver}.0.${Math.floor(Math.random()*5000)}.0 Safari/537.36`;
    generated.push(ua);
  }
  fs.writeFileSync('ua.txt', generated.join('\n'));
  userAgents = generated;
} else {
  userAgents = fs.readFileSync('ua.txt', 'utf-8').split('\n').filter(Boolean);
}

const walletFile = 'wallet_sol.json';
const openFile = 'open.json';
let walletData = [];
let openData = {};

if (fs.existsSync(walletFile)) {
  const data = JSON.parse(fs.readFileSync(walletFile, 'utf-8'));
  walletData = Array.isArray(data) ? data : [];
}

if (fs.existsSync(openFile)) {
  try {
    openData = JSON.parse(fs.readFileSync(openFile, 'utf-8'));
  } catch (err) {
    openData = {};
    console.log(colors.yellow('[!] Error reading open.json, creating new.'));
  }
}

const sleep = ms => new Promise(res => setTimeout(res, ms));

function parseProxy(proxyString) {
  const match = proxyString.match(/^https?:\/\/([^:]+):([^@]+)@([^:]+):(\d+)$/);
  if (match) {
    return { host: match[3], port: parseInt(match[4]), username: match[1], password: match[2] };
  }
  const parts = proxyString.split(':');
  if (parts.length === 4) {
    return { host: parts[0], port: parseInt(parts[1]), username: parts[2], password: parts[3] };
  }
  throw new Error(`Invalid proxy format: ${proxyString}`);
}

function signMessage(message, privateKey) {
  try {
    const messageBytes = new TextEncoder().encode(message);
    const keypair = Keypair.fromSecretKey(bs58.decode(privateKey));
    const signature = nacl.sign.detached(messageBytes, keypair.secretKey);
    return Buffer.from(signature).toString('base64');
  } catch (error) {
    throw new Error(`Signing failed: ${error.message}`);
  }
}

function getNFTInfo(templateId) {
  const rarityMap = {
    'labubu-00000-1': { name: 'Blooming Spirit', rarity: 'NFT 10x', color: colors.green },
    'labubu-00000-2': { name: 'Wise Spirit', rarity: 'NFT 10x', color: colors.green },
    'labubu-00000-3': { name: 'Guardian Spirit', rarity: 'NFT 10x', color: colors.green },
    'labubu-00000-4': { name: 'Midnight Spirit', rarity: 'NFT 100x', color: colors.yellow },
    'labubu-00000-5': { name: 'Starlight Angel', rarity: 'NFT 1000x', color: colors.magenta }
  };
  return rarityMap[templateId] || { name: 'Unknown', rarity: 'Unknown', color: colors.gray };
}

async function getBrowserSession(proxyConfig, userAgent, targetUrl = 'https://bubuverse.fun/space') {
  let browser;
  try {
    browser = await puppeteer.launch({
      headless: 'new',
      args: ['--no-sandbox', '--disable-setuid-sandbox', `--proxy-server=${proxyConfig.host}:${proxyConfig.port}`]
    });
    const page = await browser.newPage();
    await page.setViewport({ width: 1024, height: 768 });
    if (proxyConfig.username && proxyConfig.password) {
      await page.authenticate({ username: proxyConfig.username, password: proxyConfig.password });
    }
    await page.setUserAgent(userAgent);
    await page.goto(targetUrl, { waitUntil: 'networkidle2', timeout: 60000 });
    await sleep(15000);
    const pageTitle = await page.title();
    const currentUrl = page.url();
    if (!currentUrl.includes('bubuverse.fun')) {
      throw new Error(`Redirected to: ${currentUrl}`);
    }
    if (pageTitle && (pageTitle.toLowerCase().includes('error') || pageTitle.toLowerCase().includes('blocked'))) {
      throw new Error(`Error page: ${pageTitle}`);
    }
    const cookies = await page.cookies();
    let cookieString = cookies.map(cookie => `${cookie.name}=${cookie.value}`).join('; ');
    const vcrcsCookie = cookies.find(c => c.name === '_vcrcs');
    return { page, browser, cookies: cookieString, vcrcsCookie: vcrcsCookie ? vcrcsCookie.value : null };
  } catch (error) {
    if (browser) await browser.close();
    throw error;
  }
}

// Wallet Creation
async function createWallets() {
  const referrerAddress = readline.question(colors.yellow('Enter referrer address: '));
  const count = parseInt(readline.question(colors.yellow('Enter number of wallets to create: ')));
  console.log(colors.blue(`Loaded ${proxies.length} proxies and ${userAgents.length} user agents`));
  console.log(colors.yellow(`Each wallet will use a unique proxy to avoid IP bans`));

  for (let i = 0; i < count; i++) {
    console.log(colors.cyan(`\n[${i + 1}/${count}] === CREATING NEW WALLET ===`));
    if (i >= proxies.length) {
      console.log(colors.red(`[!] Out of proxies! Only ${proxies.length} available for ${count} wallets`));
      break;
    }
    const proxyString = proxies[i].trim();
    const userAgent = userAgents[Math.floor(Math.random() * userAgents.length)];
    const deviceId = uuidv4().replace(/-/g, '');
    const mnemonic = bip39.generateMnemonic(128);
    const seed = bip39.mnemonicToSeedSync(mnemonic);
    const path = "m/44'/501'/0'/0'";
    const derived = ed25519.derivePath(path, seed.toString('hex')).key;
    const keypair = Keypair.fromSeed(derived);
    const publicKey = keypair.publicKey.toBase58();
    const privateKey = bs58.encode(keypair.secretKey);

    console.log(`Creating wallet: ${publicKey}`);
    console.log(`Proxy #${i + 1}: ${proxyString}`);
    console.log(`Device ID: ${deviceId}`);

    try {
      const proxyConfig = parseProxy(proxyString);
      const session = await getBrowserSession(proxyConfig, userAgent);
      const response = await session.page.evaluate(async ({ publicKey, referrerAddress, deviceId, cookieValue }) => {
        try {
          const res = await fetch('https://bubuverse.fun/api/users', {
            method: 'POST',
            headers: {
              'accept': '*/*',
              'content-type': 'application/json',
              'cookie': `_vcrcs=${cookieValue}`
            },
            body: JSON.stringify({ walletAddress: publicKey, referrerAddress, deviceId })
          });
          const responseText = await res.text();
          let json;
          try {
            json = JSON.parse(responseText);
          } catch (e) {
            json = { error: 'Invalid JSON response', raw: responseText.substring(0, 200) };
          }
          return { status: res.status, ok: res.ok, body: json };
        } catch (error) {
          return { status: 0, ok: false, body: { error: error.message } };
        }
      }, { publicKey, referrerAddress, deviceId, cookieValue: session.vcrcsCookie });

      if (response.ok) {
        walletData.push({ mnemonic, privateKey, publicKey, deviceId, userAgent });
        fs.writeFileSync(walletFile, JSON.stringify(walletData, null, 2));
        console.log(colors.green(`[+] Success! Wallet: ${publicKey}`));
      } else {
        console.log(colors.red(`[!] Server error: ${response.status}`));
        console.log(colors.gray('Response:', JSON.stringify(response.body, null, 2)));
      }
      await session.browser.close();
    } catch (err) {
      console.log(colors.red(`[!] Error creating wallet: ${err.message || err}`));
    }
    const delayTime = Math.random() * 7000 + 5000;
    console.log(colors.gray(`Waiting ${Math.round(delayTime/1000)}s...`));
    await sleep(delayTime);
  }
  console.log(colors.green('\nDone. Wallets saved to wallet_sol.json'));
  console.log(colors.cyan(`Total created: ${walletData.length} wallets`));
}

// Daily Check-in
async function checkDailyStatus(page, walletAddress) {
  try {
    const timestamp = Date.now();
    const apiUrl = `https://bubuverse.fun/api/users/${walletAddress}/check-in-status?_t=${timestamp}`;
    const response = await page.evaluate(async (url) => {
      const res = await fetch(url, { method: 'GET', headers: { 'accept': '*/*' }, credentials: 'include' });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      return await res.json();
    }, apiUrl);
    return response;
  } catch (error) {
    throw new Error(`Failed to check daily status: ${error.message}`);
  }
}

async function performDailyCheckIn(page, walletAddress) {
  try {
    const apiUrl = `https://bubuverse.fun/api/users/${walletAddress}/check-in`;
    const response = await page.evaluate(async (url) => {
      const res = await fetch(url, { method: 'POST', headers: { 'accept': '*/*' }, credentials: 'include' });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      return await res.json();
    }, apiUrl);
    return response;
  } catch (error) {
    throw new Error(`Failed to perform daily check-in: ${error.message}`);
  }
}

async function checkNFTStats(page, walletAddress) {
  try {
    const apiUrl = `https://bubuverse.fun/api/users/${walletAddress}/nfts/stats`;
    const response = await page.evaluate(async (url) => {
      const res = await fetch(url, { method: 'GET', headers: { 'accept': '*/*' }, credentials: 'include' });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      return await res.json();
    }, apiUrl);
    return response;
  } catch (error) {
    throw new Error(`Failed to check NFT stats: ${error.message}`);
  }
}

async function collectEnergy(page, walletAddress, privateKey) {
  try {
    const timestamp = Date.now();
    const message = `Collect energy at ${timestamp}`;
    const signature = signMessage(message, privateKey);
    const body = { signature, message };
    const apiUrl = `https://bubuverse.fun/api/users/${walletAddress}/nfts/collect-energy`;
    const response = await page.evaluate(async (url, requestBody) => {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'accept': '*/*', 'content-type': 'application/json' },
        body: JSON.stringify(requestBody),
        credentials: 'include'
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      return await res.json();
    }, apiUrl, body);
    return response;
  } catch (error) {
    throw new Error(`Failed to collect energy: ${error.message}`);
  }
}

function isAlreadyCheckedInToday(wallet) {
  if (!wallet.lastCheckinDate) return false;
  const today = new Date().toDateString();
  const lastCheckin = new Date(wallet.lastCheckinDate).toDateString();
  return today === lastCheckin;
}

function markAsCheckedIn(wallet) {
  wallet.lastCheckinDate = new Date().toISOString();
  wallet.hasCollectedToday = true;
}

async function processDailyCheckIn(wallet, proxyString, walletIndex, totalWallets) {
  const { privateKey, publicKey, userAgent } = wallet;
  console.log(`\n[${walletIndex + 1}/${totalWallets}] ${colors.cyan(publicKey.substring(0, 8))}...`);
  let proxyConfig;
  try {
    proxyConfig = parseProxy(proxyString);
    console.log(`Proxy: ${colors.blue(proxyConfig.host + ':' + proxyConfig.port)}`);
  } catch (error) {
    console.log(colors.red(`Proxy error: ${error.message}`));
    return false;
  }
  let sessionData;
  try {
    console.log(colors.yellow('Fetching cookies...'));
    sessionData = await getBrowserSession(proxyConfig, userAgent, 'https://bubuverse.fun/tasks');
    console.log(colors.green('Cookies fetched successfully'));
  } catch (error) {
    console.log(colors.red(`Cookie error: ${error.message}`));
    return false;
  }
  try {
    if (!isAlreadyCheckedInToday(wallet)) {
      console.log(colors.yellow('Checking daily check-in status...'));
      const checkInStatus = await checkDailyStatus(sessionData.page, publicKey);
      if (checkInStatus.can_check_in) {
        console.log(colors.yellow('Performing daily check-in...'));
        const checkInResult = await performDailyCheckIn(sessionData.page, publicKey);
        if (checkInResult.success) {
          console.log(colors.green(`✓ Check-in successful! Received ${checkInResult.energy_reward} energy (Day ${checkInResult.check_in_count})`));
          markAsCheckedIn(wallet);
          console.log(colors.yellow('Checking energy after check-in...'));
          const nftStats = await checkNFTStats(sessionData.page, publicKey);
          if (nftStats.success && nftStats.data && nftStats.data.pending_energy > 0) {
            console.log(colors.green(`Found ${nftStats.data.pending_energy.toFixed(2)} energy to collect`));
            const collectResult = await collectEnergy(sessionData.page, publicKey, privateKey);
            if (collectResult.success) {
              const { total_nfts, success_count, failed_count, total_energy } = collectResult.data;
              console.log(colors.green(`✓ Collected ${total_energy.toFixed(2)} energy from ${success_count}/${total_nfts} NFTs`));
              if (failed_count > 0) {
                console.log(colors.yellow(`⚠ ${failed_count} NFTs failed`));
              }
            } else {
              console.log(colors.red('✗ Failed to collect energy'));
            }
          } else {
            console.log(colors.gray(`No energy to collect (${nftStats.data?.pending_energy ? nftStats.data.pending_energy.toFixed(2) : 0})`));
          }
        } else {
          console.log(colors.red('✗ Check-in failed'));
        }
      } else {
        console.log(colors.gray('Already checked in today'));
        markAsCheckedIn(wallet);
      }
    } else {
      console.log(colors.gray('Skipped - already checked in today'));
    }
    await sessionData.browser.close();
    return true;
  } catch (error) {
    console.log(colors.red(`Processing error: ${error.message}`));
    if (sessionData && sessionData.browser) await sessionData.browser.close();
    return false;
  }
}

async function dailyCheckIn() {
  if (!fs.existsSync(walletFile)) {
    console.log(colors.red(`File ${walletFile} does not exist!`));
    return;
  }
  const walletRawData = JSON.parse(fs.readFileSync(walletFile, 'utf-8'));
  const wallets = Array.isArray(walletRawData) ? walletRawData : [];
  if (wallets.length === 0) {
    console.log(colors.red('No wallets found in file!'));
    return;
  }
  if (wallets.length > proxies.length) {
    console.log(colors.red(`Not enough proxies! Need ${wallets.length}, have ${proxies.length}`));
    return;
  }
  console.log(colors.green(`Processing daily tasks for ${wallets.length} wallets with ${proxies.length} proxies`));
  console.log(colors.yellow('Checking wallets...'));
  for (let i = 0; i < wallets.length; i++) {
    const wallet = wallets[i];
    if (!wallet.deviceId) wallet.deviceId = uuidv4().replace(/-/g, '');
    if (!wallet.userAgent) wallet.userAgent = userAgents[Math.floor(Math.random() * userAgents.length)];
  }
  fs.writeFileSync(walletFile, JSON.stringify(wallets, null, 2));
  console.log(colors.green('Wallet check complete'));
  let totalProcessed = 0, totalErrors = 0;
  for (let i = 0; i < wallets.length; i++) {
    const processedSuccessfully = await processDailyCheckIn(wallets[i], proxies[i], i, wallets.length);
    if (processedSuccessfully) totalProcessed++;
    else totalErrors++;
    fs.writeFileSync(walletFile, JSON.stringify(wallets, null, 2));
    if (i < wallets.length - 1) {
      console.log(colors.gray('Waiting 3s...'));
      await sleep(3000);
    }
  }
  console.log(colors.cyan('\nSummary:'));
  console.log(colors.green(`Processed: ${totalProcessed}/${wallets.length} wallets`));
  console.log(colors.red(`Errors: ${totalErrors} wallets`));
  console.log(colors.green('Daily tasks completed!'));
}

// Open Box
async function getBoxesWithPuppeteer(page, walletAddress) {
  try {
    const timestamp = Date.now();
    const apiUrl = `https://bubuverse.fun/api/users/${walletAddress}/blind-boxes?status=unopened&_t=${timestamp}`;
    const response = await page.evaluate(async (url) => {
      const res = await fetch(url, { method: 'GET', headers: { 'accept': '*/*', 'referer': 'https://bubuverse.fun/space' }, credentials: 'include' });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      return await res.json();
    }, apiUrl);
    return response.data || [];
  } catch (error) {
    throw new Error(`Failed to get boxes: ${error.message}`);
  }
}

async function openBoxWithPuppeteer(page, walletAddress, privateKey, boxId) {
  try {
    const timestamp = Date.now();
    const message = `Open blind box ${boxId} at ${timestamp}`;
    const signature = signMessage(message, privateKey);
    const body = { box_id: boxId, signature, message };
    const apiUrl = `https://bubuverse.fun/api/users/${walletAddress}/blind-boxes/open`;
    const response = await page.evaluate(async (url, requestBody) => {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'accept': '*/*', 'content-type': 'application/json', 'referer': 'https://bubuverse.fun/space' },
        body: JSON.stringify(requestBody),
        credentials: 'include'
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      return await res.json();
    }, apiUrl, body);
    return response;
  } catch (error) {
    throw new Error(`Failed to open box: ${error.message}`);
  }
}

function hasNFT(walletAddress) {
  return openData[walletAddress] && openData[walletAddress].length > 0;
}

async function processOpenBox(wallet, proxyString, walletIndex, totalWallets) {
  const { privateKey, publicKey, userAgent } = wallet;
  console.log(`\n[${walletIndex + 1}/${totalWallets}] ${colors.cyan(publicKey.substring(0, 8))}...`);
  let proxyConfig;
  try {
    proxyConfig = parseProxy(proxyString);
    console.log(`Proxy: ${colors.blue(proxyConfig.host + ':' + proxyConfig.port)}`);
  } catch (error) {
    console.log(colors.red(`Proxy error: ${error.message}`));
    return false;
  }
  let sessionData;
  try {
    console.log(colors.yellow('Fetching cookies...'));
    sessionData = await getBrowserSession(proxyConfig, userAgent);
    console.log(colors.green('Cookies fetched successfully'));
  } catch (error) {
    console.log(colors.red(`Cookie error: ${error.message}`));
    return false;
  }
  try {
    console.log(colors.yellow('Checking boxes...'));
    const boxes = await getBoxesWithPuppeteer(sessionData.page, publicKey);
    if (boxes.length === 0) {
      console.log(colors.gray('No boxes found'));
      await sessionData.browser.close();
      return true;
    }
    console.log(colors.green(`Found ${boxes.length} boxes`));
    if (!openData[publicKey]) openData[publicKey] = [];
    let successCount = 0, failCount = 0;
    for (let i = 0; i < boxes.length; i++) {
      const box = boxes[i];
      console.log(colors.yellow(`Opening box ${i + 1}/${boxes.length}...`));
      try {
        const result = await openBoxWithPuppeteer(sessionData.page, publicKey, privateKey, box.id);
        const templateId = result.template_id;
        openData[publicKey].push(templateId);
        const nftInfo = getNFTInfo(templateId);
        console.log(nftInfo.color(`  → ${nftInfo.rarity} - ${nftInfo.name}`));
        successCount++;
        if (i < boxes.length - 1) await sleep(2000);
      } catch (error) {
        console.log(colors.red(`  → Error: ${error.message}`));
        failCount++;
        if (i < boxes.length - 1) await sleep(2000);
      }
    }
    console.log(colors.green(`Completed: ${successCount} OK, ${failCount} errors`));
    fs.writeFileSync(openFile, JSON.stringify(openData, null, 2));
    await sessionData.browser.close();
    return true;
  } catch (error) {
    console.log(colors.red(`Processing error: ${error.message}`));
    if (sessionData && sessionData.browser) await sessionData.browser.close();
    return false;
  }
}

async function openBoxes() {
  if (!fs.existsSync(walletFile)) {
    console.log(colors.red(`File ${walletFile} does not exist!`));
    return;
  }
  const walletRawData = JSON.parse(fs.readFileSync(walletFile, 'utf-8'));
  const wallets = Array.isArray(walletRawData) ? walletRawData : [];
  if (wallets.length === 0) {
    console.log(colors.red('No wallets found in file!'));
    return;
  }
  if (wallets.length > proxies.length) {
    console.log(colors.red(`Not enough proxies! Need ${wallets.length}, have ${proxies.length}`));
    return;
  }
  console.log(colors.green(`Processing ${wallets.length} wallets with ${proxies.length} proxies`));
  console.log(colors.yellow('Pre-processing wallets...'));
  for (let i = 0; i < wallets.length; i++) {
    const wallet = wallets[i];
    delete wallet.createdAt;
    delete wallet.cookieExpiresAt;
    delete wallet.cookieCreatedAt;
    delete wallet.vcrcsCookie;
    delete wallet.allCookies;
    if (!wallet.deviceId) wallet.deviceId = uuidv4().replace(/-/g, '');
    if (!wallet.userAgent) wallet.userAgent = userAgents[Math.floor(Math.random() * userAgents.length)];
  }
  fs.writeFileSync(walletFile, JSON.stringify(wallets, null, 2));
  console.log(colors.green('Pre-processing complete'));
  for (let i = 0; i < wallets.length; i++) {
    const wallet = wallets[i];
    if (hasNFT(wallet.publicKey)) {
      const nftInfo = getNFTInfo(openData[wallet.publicKey][0]);
      console.log(`\n[${i + 1}/${wallets.length}] ${colors.cyan(wallet.publicKey.substring(0, 8))}...`);
      console.log(colors.gray(`Skipped - already has ${nftInfo.rarity}`));
      await sleep(1000);
      continue;
    }
    const processedSuccessfully = await processOpenBox(wallet, proxies[i], i, wallets.length);
    fs.writeFileSync(walletFile, JSON.stringify(wallets, null, 2));
    if (i < wallets.length - 1) {
      console.log(colors.gray('Waiting 3s...'));
      await sleep(3000);
    }
  }
  showBoxStats();
  console.log(colors.green('Completed!'));
}

function showBoxStats() {
  console.log(colors.cyan('\n=== Statistics ==='));
  if (Object.keys(openData).length === 0) {
    console.log(colors.gray('No data available'));
    return;
  }
  let totalBoxes = 0;
  const rarityCount = { '10x': 0, '100x': 0, '1000x': 0 };
  for (const [, templates] of Object.entries(openData)) {
    templates.forEach(templateId => {
      totalBoxes++;
      const nftInfo = getNFTInfo(templateId);
      if (nftInfo.rarity.includes('10x')) rarityCount['10x']++;
      else if (nftInfo.rarity.includes('100x')) rarityCount['100x']++;
      else if (nftInfo.rarity.includes('1000x')) rarityCount['1000x']++;
    });
  }
  console.log(colors.cyan('\nSummary:'));
  console.log(colors.green(`NFT 10x: ${rarityCount['10x']}`));
  console.log(colors.yellow(`NFT 100x: ${rarityCount['100x']}`));
  console.log(colors.magenta(`NFT 1000x: ${rarityCount['1000x']}`));
  console.log(colors.blue(`Total boxes: ${totalBoxes}`));
}

// NFT Stake
async function stakeNFTs(page, walletAddress, privateKey) {
  try {
    const timestamp = Date.now();
    const message = `Stake NFTs at ${timestamp}`;
    const signature = signMessage(message, privateKey);
    const body = { signature, message };
    const apiUrl = `https://bubuverse.fun/api/users/${walletAddress}/nfts/stake`;
    const response = await page.evaluate(async (url, requestBody) => {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'accept': '*/*', 'content-type': 'application/json' },
        body: JSON.stringify(requestBody),
        credentials: 'include'
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      return await res.json();
    }, apiUrl, body);
    return response;
  } catch (error) {
    throw new Error(`Failed to stake NFTs: ${error.message}`);
  }
}

function isAlreadyStaked(walletAddress) {
  return openData[walletAddress] && openData[walletAddress].some(nft =>
    typeof nft === 'object' && nft.staked === true
  );
}

function markAsStaked(walletAddress, stakeResult) {
  if (!openData[walletAddress]) openData[walletAddress] = [];
  openData[walletAddress] = openData[walletAddress].map(nft => {
    if (typeof nft === 'string') {
      return { templateId: nft, staked: true, stakedAt: new Date().toISOString(), stakeResult };
    } else if (typeof nft === 'object' && !nft.staked) {
      return { ...nft, staked: true, stakedAt: new Date().toISOString(), stakeResult };
    }
    return nft;
  });
}

async function processStakeNFT(wallet, proxyString, walletIndex, totalWallets) {
  const { privateKey, publicKey, userAgent } = wallet;
  console.log(`\n[${walletIndex + 1}/${totalWallets}] ${colors.cyan(publicKey.substring(0, 8))}...`);
  let proxyConfig;
  try {
    proxyConfig = parseProxy(proxyString);
    console.log(`Proxy: ${colors.blue(proxyConfig.host + ':' + proxyConfig.port)}`);
  } catch (error) {
    console.log(colors.red(`Proxy error: ${error.message}`));
    return false;
  }
  let sessionData;
  try {
    console.log(colors.yellow('Fetching cookies...'));
    sessionData = await getBrowserSession(proxyConfig, userAgent);
    console.log(colors.green('Cookies fetched successfully'));
  } catch (error) {
    console.log(colors.red(`Cookie error: ${error.message}`));
    return false;
  }
  try {
    if (!hasNFT(publicKey)) {
      console.log(colors.gray('No NFTs to stake'));
      await sessionData.browser.close();
      return true;
    }
    if (isAlreadyStaked(publicKey)) {
      console.log(colors.gray('NFTs already staked'));
      await sessionData.browser.close();
      return true;
    }
    console.log(colors.yellow('Staking NFTs...'));
    const stakeResult = await stakeNFTs(sessionData.page, publicKey, privateKey);
    if (stakeResult.success) {
      const { total_nfts, success_count, failed_count } = stakeResult.data;
      console.log(colors.green(`Stake successful: ${success_count}/${total_nfts} NFTs`));
      if (failed_count > 0) {
        console.log(colors.red(`Errors: ${failed_count} NFTs failed`));
        if (stakeResult.data.error_messages && stakeResult.data.error_messages.length > 0) {
          stakeResult.data.error_messages.forEach(msg => console.log(colors.red(`  → ${msg}`)));
        }
      }
      markAsStaked(publicKey, { total_nfts, success_count, failed_count, timestamp: new Date().toISOString() });
      fs.writeFileSync(openFile, JSON.stringify(openData, null, 2));
    } else {
      console.log(colors.red('Stake failed'));
    }
    await sessionData.browser.close();
    return true;
  } catch (error) {
    console.log(colors.red(`Stake error: ${error.message}`));
    if (sessionData && sessionData.browser) await sessionData.browser.close();
    return false;
  }
}

async function stakeNFTsProcess() {
  if (!fs.existsSync(walletFile)) {
    console.log(colors.red(`File ${walletFile} does not exist!`));
    return;
  }
  const walletRawData = JSON.parse(fs.readFileSync(walletFile, 'utf-8'));
  const wallets = Array.isArray(walletRawData) ? walletRawData : [];
  if (wallets.length === 0) {
    console.log(colors.red('No wallets found in file!'));
    return;
  }
  if (wallets.length > proxies.length) {
    console.log(colors.red(`Not enough proxies! Need ${wallets.length}, have ${proxies.length}`));
    return;
  }
  console.log(colors.green(`Staking NFTs for ${wallets.length} wallets with ${proxies.length} proxies`));
  console.log(colors.yellow('Checking wallets...'));
  for (let i = 0; i < wallets.length; i++) {
    const wallet = wallets[i];
    if (!wallet.deviceId) wallet.deviceId = uuidv4().replace(/-/g, '');
    if (!wallet.userAgent) wallet.userAgent = userAgents[Math.floor(Math.random() * userAgents.length)];
  }
  fs.writeFileSync(walletFile, JSON.stringify(wallets, null, 2));
  console.log(colors.green('Wallet check complete'));
  let totalStaked = 0, totalSkipped = 0, totalErrors = 0;
  for (let i = 0; i < wallets.length; i++) {
    const wallet = wallets[i];
    if (isAlreadyStaked(wallet.publicKey)) {
      console.log(`\n[${i + 1}/${wallets.length}] ${colors.cyan(wallet.publicKey.substring(0, 8))}...`);
      console.log(colors.gray('Skipped - already staked'));
      totalSkipped++;
      await sleep(1000);
      continue;
    }
    if (!hasNFT(wallet.publicKey)) {
      console.log(`\n[${i + 1}/${wallets.length}] ${colors.cyan(wallet.publicKey.substring(0, 8))}...`);
      console.log(colors.gray('Skipped - no NFTs'));
      totalSkipped++;
      await sleep(1000);
      continue;
    }
    const processedSuccessfully = await processStakeNFT(wallet, proxies[i], i, wallets.length);
    if (processedSuccessfully && isAlreadyStaked(wallet.publicKey)) totalStaked++;
    else totalErrors++;
    fs.writeFileSync(walletFile, JSON.stringify(wallets, null, 2));
    if (i < wallets.length - 1) {
      console.log(colors.gray('Waiting 3s...'));
      await sleep(3000);
    }
  }
  showStakeStats(totalStaked, totalSkipped, totalErrors);
  console.log(colors.green('Completed!'));
}

function showStakeStats(totalStaked, totalSkipped, totalErrors) {
  if (Object.keys(openData).length === 0) {
    console.log(colors.gray('No data available'));
    return;
  }
  let totalWallets = 0, walletsWithStakedNFTs = 0, totalNFTs = 0, totalStakedNFTs = 0;
  for (const [, nfts] of Object.entries(openData)) {
    totalWallets++;
    let walletStakedCount = 0;
    nfts.forEach(nft => {
      totalNFTs++;
      if (typeof nft === 'object' && nft.staked) walletStakedCount++, totalStakedNFTs++;
    });
    if (walletStakedCount > 0) walletsWithStakedNFTs++;
  }
  console.log(colors.cyan('\nSummary:'));
  console.log(colors.green(`Wallets with staked NFTs: ${walletsWithStakedNFTs}/${totalWallets}`));
  console.log(colors.green(`Staked NFTs: ${totalStakedNFTs}/${totalNFTs}`));
  if (totalStaked > 0 || totalSkipped > 0 || totalErrors > 0) {
    console.log(colors.blue(`This session: ${totalStaked} staked, ${totalSkipped} skipped, ${totalErrors} errors`));
  }
}

// Run All
async function runAll() {
  console.log(colors.cyan('Running all tasks sequentially...'));
  await createWallets();
  await dailyCheckIn();
  await openBoxes();
  await stakeNFTsProcess();
  console.log(colors.green('All tasks completed!'));
}

// Menu
function showMenu() {
  console.log(colors.cyan('\n=== BUBUVERSE AUTOMATION TOOL ==='));
  console.log(colors.green('1. Create Wallet'));
  console.log(colors.green('2. Daily Check-in'));
  console.log(colors.green('3. Open Box'));
  console.log(colors.green('4. NFT Stake'));
  console.log(colors.green('5. Run All'));
  console.log(colors.green('6. Exit'));
  return readline.question(colors.yellow('Select an option (1-6): '));
}

async function main() {
  console.log(colors.cyan('BUBUVERSE AUTOMATION TOOL'));
  console.log(colors.green(`Loaded ${proxies.length} proxies, ${userAgents.length} user agents`));
  while (true) {
    const choice = showMenu();
    switch (choice) {
      case '1':
        await createWallets();
        break;
      case '2':
        await dailyCheckIn();
        break;
      case '3':
        await openBoxes();
        break;
      case '4':
        await stakeNFTsProcess();
        break;
      case '5':
        await runAll();
        break;
      case '6':
        console.log(colors.green('Exiting...'));
        process.exit(0);
      default:
        console.log(colors.red('Invalid option! Please select 1-6.'));
    }
  }
}

main();

process.on('SIGINT', () => {
  console.log(colors.yellow('\nSaving data...'));
  fs.writeFileSync(walletFile, JSON.stringify(walletData, null, 2));
  fs.writeFileSync(openFile, JSON.stringify(openData, null, 2));
  console.log(colors.green('Saved wallet_sol.json and open.json'));
  showBoxStats();
  showStakeStats();
  process.exit(0);
});

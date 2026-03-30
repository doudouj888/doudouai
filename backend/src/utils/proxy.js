import fs from 'fs'
import { getDatabase } from '../database/init.js'

export const GLOBAL_PROXY_URLS_CONFIG_KEY = 'open_accounts_sweeper_proxy_urls'
const GLOBAL_PROXY_URLS_ENV_KEY = 'OPEN_ACCOUNTS_SWEEPER_PROXY_URLS'
const LEGACY_PROXY_ENV_KEYS = [
  'CHATGPT_PROXY_URL',
  'CHATGPT_PROXY',
  'ALL_PROXY',
  'all_proxy',
  'HTTPS_PROXY',
  'https_proxy',
  'HTTP_PROXY',
  'http_proxy',
]
const CACHE_TTL_MS = 60 * 1000

let cachedGlobalProxySettings = null
let cachedGlobalProxySettingsAt = 0

function dedupeEntries(entries = []) {
  const seen = new Set()
  const result = []
  for (const entry of entries) {
    const normalized = String(entry || '').trim()
    if (!normalized || seen.has(normalized)) continue
    seen.add(normalized)
    result.push(normalized)
  }
  return result
}

function splitList(value) {
  const raw = String(value || '').trim()
  if (!raw) return []

  if (raw.startsWith('[')) {
    try {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) {
        return parsed.map(item => String(item || '').trim()).filter(Boolean)
      }
    } catch {
      // fallthrough to delimiter parsing
    }
  }

  return raw
    .split(/[\n,;]+/g)
    .map(item => String(item || '').trim())
    .filter(Boolean)
}

export function parseProxyUrlEntries(value) {
  return dedupeEntries(splitList(value))
}

export function stringifyProxyUrlEntries(entries = []) {
  return dedupeEntries(entries).join('\n')
}

export function parseProxyConfig(proxyUrl) {
  if (!proxyUrl) return null

  try {
    const parsed = new URL(String(proxyUrl))
    const protocol = String(parsed.protocol || '').replace(':', '').toLowerCase()
    if (!protocol || !['http', 'https', 'socks', 'socks4', 'socks4a', 'socks5', 'socks5h'].includes(protocol)) {
      return null
    }

    if (!parsed.hostname) return null

    const defaultPort = protocol.startsWith('socks') ? 1080 : (protocol === 'https' ? 443 : 80)
    const port = parsed.port ? Number(parsed.port) : defaultPort
    if (!Number.isFinite(port) || port <= 0) return null

    const auth = parsed.username
      ? {
          username: decodeURIComponent(parsed.username),
          password: decodeURIComponent(parsed.password || '')
        }
      : undefined

    return {
      protocol,
      host: parsed.hostname,
      port,
      ...(auth ? { auth } : {})
    }
  } catch {
    return null
  }
}

export function formatProxyForLog(proxyUrl) {
  if (!proxyUrl) return ''
  try {
    const parsed = new URL(String(proxyUrl))
    const protocol = String(parsed.protocol || '').replace(':', '')
    const host = parsed.hostname || ''
    const port = parsed.port ? `:${parsed.port}` : ''
    return `${protocol}://${host}${port}`
  } catch {
    return String(proxyUrl)
  }
}

export function inspectProxyListInput(value) {
  const entries = parseProxyUrlEntries(value)
  const proxies = []
  const invalidEntries = []

  for (const entry of entries) {
    const config = parseProxyConfig(entry)
    if (!config) {
      invalidEntries.push(entry)
      continue
    }
    proxies.push({ url: entry, config })
  }

  return {
    entries,
    proxies,
    invalidEntries,
  }
}

export function loadProxyList({ urlsEnvKey, fileEnvKey } = {}) {
  const urlsKey = urlsEnvKey || GLOBAL_PROXY_URLS_ENV_KEY
  const fileKey = fileEnvKey || 'OPEN_ACCOUNTS_SWEEPER_PROXY_FILE'

  const rawUrls = process.env[urlsKey]
  const rawFile = process.env[fileKey]

  const urls = []

  if (rawFile) {
    const path = String(rawFile).trim()
    if (path) {
      try {
        const fileText = fs.readFileSync(path, 'utf8')
        for (const line of String(fileText).split('\n')) {
          const trimmed = String(line || '').trim()
          if (!trimmed || trimmed.startsWith('#')) continue
          urls.push(trimmed)
        }
      } catch (error) {
        console.warn('[ProxyList] failed to read proxy file', { path, message: error?.message || String(error) })
      }
    }
  }

  urls.push(...parseProxyUrlEntries(rawUrls))

  const { proxies, invalidEntries } = inspectProxyListInput(urls)
  for (const invalidEntry of invalidEntries) {
    console.warn('[ProxyList] invalid proxy url ignored', { proxy: formatProxyForLog(invalidEntry) })
  }

  return proxies
}

const loadSystemConfigEntry = (database, key) => {
  if (!database || !key) return { exists: false, value: '' }
  const result = database.exec(
    'SELECT config_value FROM system_config WHERE config_key = ? LIMIT 1',
    [key]
  )
  if (!result[0]?.values?.length) {
    return { exists: false, value: '' }
  }
  return {
    exists: true,
    value: String(result[0].values[0][0] ?? ''),
  }
}

export const invalidateGlobalProxySettingsCache = () => {
  cachedGlobalProxySettings = null
  cachedGlobalProxySettingsAt = 0
}

export async function getGlobalProxySettings(db, { forceRefresh = false } = {}) {
  const now = Date.now()
  if (!forceRefresh && cachedGlobalProxySettings && now - cachedGlobalProxySettingsAt < CACHE_TTL_MS) {
    return cachedGlobalProxySettings
  }

  const database = db || await getDatabase()
  const stored = loadSystemConfigEntry(database, GLOBAL_PROXY_URLS_CONFIG_KEY)
  const sourceValue = stored.exists
    ? stored.value
    : String(process.env[GLOBAL_PROXY_URLS_ENV_KEY] || '')
  const { entries, proxies } = inspectProxyListInput(sourceValue)

  cachedGlobalProxySettings = {
    proxyUrls: stringifyProxyUrlEntries(entries),
    stored: stored.exists,
    entries,
    proxies,
    effectiveCount: proxies.length,
  }
  cachedGlobalProxySettingsAt = now
  return cachedGlobalProxySettings
}

export async function loadGlobalProxyList(db, options = {}) {
  const settings = await getGlobalProxySettings(db, options)
  return settings.proxies
}

export function getLegacyProxyFromEnv() {
  for (const key of LEGACY_PROXY_ENV_KEYS) {
    const normalized = String(process.env[key] || '').trim()
    if (!normalized) continue
    const config = parseProxyConfig(normalized)
    if (!config) continue
    return { url: normalized, config }
  }
  return null
}

export async function loadDefaultProxyList(db, options = {}) {
  const proxies = await loadGlobalProxyList(db, options)
  if (proxies.length > 0) return proxies
  const legacyEntry = getLegacyProxyFromEnv()
  return legacyEntry ? [legacyEntry] : []
}

export function normalizeProxyConfig(proxy) {
  if (!proxy) return null
  if (typeof proxy === 'string') return parseProxyConfig(proxy)
  if (typeof proxy === 'object' && proxy.host && proxy.port) {
    const protocol = proxy.protocol ? String(proxy.protocol).replace(':', '').toLowerCase() : 'http'
    if (!['http', 'https', 'socks', 'socks4', 'socks4a', 'socks5', 'socks5h'].includes(protocol)) return null

    const port = Number(proxy.port)
    if (!Number.isFinite(port) || port <= 0) return null

    const auth = proxy.auth && typeof proxy.auth === 'object'
      ? {
          username: proxy.auth.username ? String(proxy.auth.username) : '',
          password: proxy.auth.password ? String(proxy.auth.password) : '',
        }
      : undefined

    return {
      protocol,
      host: String(proxy.host),
      port,
      ...(auth?.username ? { auth } : {}),
    }
  }

  return null
}

export function isSocksProxyConfig(proxyConfig) {
  if (!proxyConfig) return false
  const protocol = String(proxyConfig.protocol || '').toLowerCase()
  return protocol === 'socks' || protocol.startsWith('socks')
}

export function buildProxyUrlFromConfig(proxyConfig) {
  if (!proxyConfig) return ''
  const protocol = String(proxyConfig.protocol || '').replace(':', '')
  const host = String(proxyConfig.host || '')
  const port = Number(proxyConfig.port || 0)
  if (!protocol || !host || !Number.isFinite(port) || port <= 0) return ''

  const auth = proxyConfig.auth && typeof proxyConfig.auth === 'object'
    ? {
        username: proxyConfig.auth.username ? String(proxyConfig.auth.username) : '',
        password: proxyConfig.auth.password ? String(proxyConfig.auth.password) : '',
      }
    : null

  const authPart = auth && auth.username
    ? `${encodeURIComponent(auth.username)}:${encodeURIComponent(auth.password || '')}@`
    : ''

  return `${protocol}://${authPart}${host}:${port}`
}

let socksProxyAgentModulePromise = null
let httpProxyAgentModulePromise = null
let httpsProxyAgentModulePromise = null
const socksAgentCache = new Map()
const httpProxyAgentCache = new Map()
const httpsProxyAgentCache = new Map()

async function getSocksProxyAgentModule() {
  if (!socksProxyAgentModulePromise) {
    socksProxyAgentModulePromise = import('socks-proxy-agent')
  }
  return socksProxyAgentModulePromise
}

async function getHttpProxyAgentModule() {
  if (!httpProxyAgentModulePromise) {
    httpProxyAgentModulePromise = import('http-proxy-agent')
  }
  return httpProxyAgentModulePromise
}

async function getHttpsProxyAgentModule() {
  if (!httpsProxyAgentModulePromise) {
    httpsProxyAgentModulePromise = import('https-proxy-agent')
  }
  return httpsProxyAgentModulePromise
}

async function getSocksAgent(proxyUrl) {
  const url = String(proxyUrl || '').trim()
  if (!url) return null

  const cached = socksAgentCache.get(url)
  if (cached) return cached

  const module = await getSocksProxyAgentModule()
  const SocksProxyAgent = module?.SocksProxyAgent || module?.default
  if (!SocksProxyAgent) {
    throw new Error('SOCKS5 代理依赖 socks-proxy-agent 加载失败')
  }

  const agent = new SocksProxyAgent(url)
  socksAgentCache.set(url, agent)
  return agent
}

async function getHttpProxyAgent(proxyUrl) {
  const url = String(proxyUrl || '').trim()
  if (!url) return null

  const cached = httpProxyAgentCache.get(url)
  if (cached) return cached

  const module = await getHttpProxyAgentModule()
  const HttpProxyAgent = module?.HttpProxyAgent || module?.default
  if (!HttpProxyAgent) {
    throw new Error('HTTP 代理依赖 http-proxy-agent 加载失败')
  }

  const agent = new HttpProxyAgent(url)
  httpProxyAgentCache.set(url, agent)
  return agent
}

async function getHttpsProxyAgent(proxyUrl) {
  const url = String(proxyUrl || '').trim()
  if (!url) return null

  const cached = httpsProxyAgentCache.get(url)
  if (cached) return cached

  const module = await getHttpsProxyAgentModule()
  const HttpsProxyAgent = module?.HttpsProxyAgent || module?.default
  if (!HttpsProxyAgent) {
    throw new Error('HTTPS 代理依赖 https-proxy-agent 加载失败')
  }

  const agent = new HttpsProxyAgent(url)
  httpsProxyAgentCache.set(url, agent)
  return agent
}

export async function buildAxiosProxyOptions(proxy) {
  const proxyConfig = normalizeProxyConfig(proxy)
  if (!proxyConfig) {
    return {
      proxy: false,
      httpAgent: undefined,
      httpsAgent: undefined,
    }
  }

  const proxyUrl = typeof proxy === 'string'
    ? String(proxy).trim()
    : buildProxyUrlFromConfig(proxyConfig)

  if (isSocksProxyConfig(proxyConfig)) {
    const socksAgent = await getSocksAgent(proxyUrl)
    return {
      proxy: false,
      httpAgent: socksAgent || undefined,
      httpsAgent: socksAgent || undefined,
    }
  }

  // Avoid Axios' built-in proxy mode here. Explicit agents properly tunnel
  // HTTPS upstream traffic through both HTTP and HTTPS proxies via CONNECT.
  const [httpAgent, httpsAgent] = await Promise.all([
    getHttpProxyAgent(proxyUrl),
    getHttpsProxyAgent(proxyUrl),
  ])

  return {
    proxy: false,
    httpAgent: httpAgent || undefined,
    httpsAgent: httpsAgent || undefined,
  }
}

const fnv1a32 = (value) => {
  const input = String(value ?? '')
  let hash = 0x811c9dc5
  for (let i = 0; i < input.length; i += 1) {
    hash ^= input.charCodeAt(i)
    hash = Math.imul(hash, 0x01000193) >>> 0
  }
  return hash >>> 0
}

export function pickProxyByHash(proxies = [], key, { attempt = 1 } = {}) {
  const list = Array.isArray(proxies) ? proxies : []
  if (list.length === 0) return null

  const normalizedKey = String(key ?? '').trim()
  const attemptOffset = Math.max(0, Number(attempt || 1) - 1)

  if (!normalizedKey) {
    return list[attemptOffset % list.length] || null
  }

  const base = fnv1a32(normalizedKey)
  const index = (base + attemptOffset) % list.length
  return list[index] || null
}

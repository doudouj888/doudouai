import { getDatabase } from '../database/init.js'

const CONFIG_KEYS = ['public_base_url']
const CACHE_TTL_MS = 60 * 1000

let cachedSettings = null
let cachedAt = 0

export const normalizePublicBaseUrl = (value) => {
  const raw = String(value || '').trim()
  if (!raw) return ''

  try {
    const parsed = new URL(raw)
    if (!['http:', 'https:'].includes(parsed.protocol)) return ''
    const normalizedPath = parsed.pathname === '/' ? '' : parsed.pathname.replace(/\/+$/, '')
    return `${parsed.origin}${normalizedPath}`
  } catch {
    return ''
  }
}

const loadSystemConfigMap = (database, keys) => {
  if (!database) return new Map()
  const list = Array.isArray(keys) && keys.length ? keys : CONFIG_KEYS
  const placeholders = list.map(() => '?').join(',')
  const result = database.exec(
    `SELECT config_key, config_value FROM system_config WHERE config_key IN (${placeholders})`,
    list
  )
  const map = new Map()
  const rows = result[0]?.values || []
  for (const row of rows) {
    map.set(String(row?.[0] ?? ''), String(row?.[1] ?? ''))
  }
  return map
}

export const getPublicBaseUrlFromEnv = () => normalizePublicBaseUrl(process.env.PUBLIC_BASE_URL || '')

export const invalidatePublicBaseUrlCache = () => {
  cachedSettings = null
  cachedAt = 0
}

export async function getPublicBaseUrlSettings(db, { forceRefresh = false } = {}) {
  const now = Date.now()
  if (!forceRefresh && cachedSettings && now - cachedAt < CACHE_TTL_MS) {
    return cachedSettings
  }

  const database = db || await getDatabase()
  const stored = loadSystemConfigMap(database, CONFIG_KEYS)
  const envBaseUrl = getPublicBaseUrlFromEnv()
  const baseUrl = stored.has('public_base_url')
    ? normalizePublicBaseUrl(stored.get('public_base_url'))
    : envBaseUrl

  cachedSettings = {
    baseUrl,
    stored: {
      baseUrl: stored.has('public_base_url')
    }
  }
  cachedAt = now
  return cachedSettings
}

export async function resolvePublicBaseUrl(req, db) {
  const settings = await getPublicBaseUrlSettings(db)
  if (settings.baseUrl) return settings.baseUrl

  const protoHeader = req?.headers?.['x-forwarded-proto']
  const protocol = typeof protoHeader === 'string' && protoHeader.trim()
    ? protoHeader.split(',')[0].trim()
    : (req?.protocol || 'https')
  const host = typeof req?.get === 'function' ? req.get('host') : ''
  if (!host) return ''
  return `${protocol}://${host}`
}

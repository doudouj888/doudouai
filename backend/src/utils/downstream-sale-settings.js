import { getDatabase } from '../database/init.js'

const CONFIG_KEYS = [
  'downstream_sale_enabled',
  'downstream_sale_product_name',
  'downstream_sale_amount',
  'downstream_sale_pay_alipay_enabled',
  'downstream_sale_pay_wxpay_enabled'
]

const DEFAULTS = {
  enabled: false,
  productName: '下游渠道兑换码',
  amount: '9.90',
  payAlipayEnabled: true,
  payWxpayEnabled: false
}

const CACHE_TTL_MS = 60 * 1000
let cachedSettings = null
let cachedAt = 0

const parseBool = (value, fallback = false) => {
  if (value === undefined || value === null) return fallback
  if (typeof value === 'boolean') return value
  const normalized = String(value).trim().toLowerCase()
  if (!normalized) return fallback
  return ['true', '1', 'yes', 'y', 'on'].includes(normalized)
}

const normalizeAmount = (value, fallback = DEFAULTS.amount) => {
  const parsed = Number.parseFloat(String(value ?? '').trim())
  if (!Number.isFinite(parsed) || parsed <= 0) return fallback
  return (Math.round(parsed * 100) / 100).toFixed(2)
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

export const invalidateDownstreamSaleSettingsCache = () => {
  cachedSettings = null
  cachedAt = 0
}

export async function getDownstreamSaleSettings(db, { forceRefresh = false } = {}) {
  const now = Date.now()
  if (!forceRefresh && cachedSettings && now - cachedAt < CACHE_TTL_MS) {
    return cachedSettings
  }

  const database = db || (await getDatabase())
  const stored = loadSystemConfigMap(database, CONFIG_KEYS)

  const resolveString = (key, fallback) => {
    if (!stored.has(key)) return fallback
    return String(stored.get(key) ?? '')
  }

  cachedSettings = {
    enabled: parseBool(resolveString('downstream_sale_enabled', DEFAULTS.enabled), DEFAULTS.enabled),
    productName: String(resolveString('downstream_sale_product_name', DEFAULTS.productName) || '').trim() || DEFAULTS.productName,
    amount: normalizeAmount(resolveString('downstream_sale_amount', DEFAULTS.amount), DEFAULTS.amount),
    payAlipayEnabled: parseBool(
      resolveString('downstream_sale_pay_alipay_enabled', DEFAULTS.payAlipayEnabled),
      DEFAULTS.payAlipayEnabled
    ),
    payWxpayEnabled: parseBool(
      resolveString('downstream_sale_pay_wxpay_enabled', DEFAULTS.payWxpayEnabled),
      DEFAULTS.payWxpayEnabled
    ),
    stored: {
      enabled: stored.has('downstream_sale_enabled'),
      productName: stored.has('downstream_sale_product_name'),
      amount: stored.has('downstream_sale_amount'),
      payAlipayEnabled: stored.has('downstream_sale_pay_alipay_enabled'),
      payWxpayEnabled: stored.has('downstream_sale_pay_wxpay_enabled')
    }
  }
  cachedAt = now
  return cachedSettings
}

import { getDatabase } from '../database/init.js'
import { getSystemConfigValue } from './system-config.js'

export const TEAM_CAPACITY_CONFIG_KEY = 'team_capacity_limit'
export const DEFAULT_TEAM_CAPACITY_LIMIT = 5
const MIN_TEAM_CAPACITY_LIMIT = 1
const MAX_TEAM_CAPACITY_LIMIT = 999
const CACHE_TTL_MS = 30 * 1000

let cachedSettings = null
let cachedAt = 0

const toInt = (value, fallback) => {
  const parsed = Number.parseInt(String(value ?? ''), 10)
  return Number.isFinite(parsed) ? parsed : fallback
}

export const normalizeTeamCapacityLimit = (value, fallback = DEFAULT_TEAM_CAPACITY_LIMIT) => {
  const envFallback = toInt(process.env.TEAM_CAPACITY_LIMIT, fallback)
  const parsed = toInt(value, envFallback)
  const normalized = Number.isFinite(parsed) ? parsed : envFallback
  return Math.max(MIN_TEAM_CAPACITY_LIMIT, Math.min(MAX_TEAM_CAPACITY_LIMIT, normalized))
}

export const getTeamCapacityLimitSync = (database, fallback = DEFAULT_TEAM_CAPACITY_LIMIT) => {
  const stored = getSystemConfigValue(database, TEAM_CAPACITY_CONFIG_KEY)
  return normalizeTeamCapacityLimit(stored, fallback)
}

export const invalidateTeamCapacitySettingsCache = () => {
  cachedSettings = null
  cachedAt = 0
}

export async function getTeamCapacitySettings(db, { forceRefresh = false } = {}) {
  const now = Date.now()
  if (!forceRefresh && cachedSettings && now - cachedAt < CACHE_TTL_MS) {
    return cachedSettings
  }

  const database = db || (await getDatabase())
  const teamCapacityLimit = getTeamCapacityLimitSync(database)

  cachedSettings = {
    teamCapacityLimit,
    stored: {
      teamCapacityLimit: getSystemConfigValue(database, TEAM_CAPACITY_CONFIG_KEY) != null
    }
  }
  cachedAt = now
  return cachedSettings
}

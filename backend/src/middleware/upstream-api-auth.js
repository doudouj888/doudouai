import crypto from 'crypto'
import { getUpstreamSettings, normalizeUpstreamPeerDomain } from '../utils/upstream-settings.js'

const normalizeKey = (value) => (typeof value === 'string' ? value.trim() : '')

const timingSafeEqual = (a, b) => {
  const left = normalizeKey(a)
  const right = normalizeKey(b)
  if (!left || !right) return false
  const leftBuf = Buffer.from(left)
  const rightBuf = Buffer.from(right)
  if (leftBuf.length !== rightBuf.length) return false
  return crypto.timingSafeEqual(leftBuf, rightBuf)
}

const getHeaderValue = (value) => {
  if (Array.isArray(value)) {
    return typeof value[0] === 'string' ? value[0] : ''
  }
  return typeof value === 'string' ? value : ''
}

const resolveRequesterDomain = (req) => {
  const candidates = [
    getHeaderValue(req.headers['x-downstream-domain']),
    getHeaderValue(req.headers['x-upstream-domain']),
    getHeaderValue(req.headers.origin),
    getHeaderValue(req.headers.referer),
    getHeaderValue(req.headers.referrer),
  ]

  for (const candidate of candidates) {
    const normalized = normalizeUpstreamPeerDomain(candidate)
    if (normalized) return normalized
  }

  return ''
}

const resolveExpectedInboundClient = (settings, requesterDomain) => {
  const clients = Array.isArray(settings?.inboundClients)
    ? settings.inboundClients.filter(client => Boolean(String(client?.apiKey || '').trim()))
    : []

  if (clients.length === 0) return null

  if (requesterDomain) {
    const exactMatch = clients.find(client => String(client?.domain || '').trim() === requesterDomain)
    if (exactMatch) return exactMatch
  }

  return clients.find(client => !String(client?.domain || '').trim()) || null
}

export async function upstreamApiAuth(req, res, next) {
  try {
    const providedKey = normalizeKey(req.headers['x-upstream-key'])
    const settings = await getUpstreamSettings()

    if (!settings.apiEnabled) {
      return res.status(503).json({ ok: false, status: 'disabled', message: '上游接口未启用' })
    }

    const requesterDomain = resolveRequesterDomain(req)
    const hasScopedInboundClients = Array.isArray(settings?.inboundClients) && settings.inboundClients.length > 0
    const inboundClient = resolveExpectedInboundClient(settings, requesterDomain)

    if (inboundClient) {
      if (!timingSafeEqual(providedKey, inboundClient.apiKey)) {
        return res.status(401).json({ ok: false, status: 'unauthorized', message: 'Unauthorized: Invalid upstream API key' })
      }

      req.upstreamRequesterDomain = requesterDomain
      req.upstreamInboundClientId = String(inboundClient.id || '')
      return next()
    }

    if (hasScopedInboundClients) {
      return res.status(401).json({ ok: false, status: 'unauthorized', message: 'Unauthorized: Unknown downstream domain' })
    }

    if (!settings.apiKey) {
      return res.status(503).json({ ok: false, status: 'disabled', message: '上游接口密钥未配置' })
    }

    if (!timingSafeEqual(providedKey, settings.apiKey)) {
      return res.status(401).json({ ok: false, status: 'unauthorized', message: 'Unauthorized: Invalid upstream API key' })
    }

    next()
  } catch (error) {
    console.error('[Upstream API] auth failed:', error)
    res.status(500).json({ ok: false, status: 'failed', message: 'Failed to validate upstream API key' })
  }
}

import express from 'express'
import { getDatabase, saveDatabase } from '../database/init.js'
import { apiKeyAuth } from '../middleware/api-key-auth.js'
import { syncAccountUserCount } from '../services/account-sync.js'
import { generateAccountClientProfile } from '../services/account-client-profile.js'

const router = express.Router()

const EXPIRE_AT_REGEX = /^\d{4}\/\d{2}\/\d{2} \d{2}:\d{2}$/

const normalizeEmail = (value) => String(value ?? '').trim().toLowerCase()

const normalizeBoolean = (value) => {
  if (typeof value === 'boolean') return value
  if (typeof value === 'number') {
    if (value === 1) return true
    if (value === 0) return false
    return null
  }
  const raw = String(value ?? '').trim().toLowerCase()
  if (!raw) return null
  if (['1', 'true', 'yes'].includes(raw)) return true
  if (['0', 'false', 'no'].includes(raw)) return false
  return null
}

const formatExpireAt = (date) => {
  try {
    return new Intl.DateTimeFormat('zh-CN', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    }).format(date)
  } catch {
    const pad = (value) => String(value).padStart(2, '0')
    return `${date.getFullYear()}/${pad(date.getMonth() + 1)}/${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
  }
}

const normalizeExpireAt = (value) => {
  if (value == null) return null
  const raw = String(value).trim()
  if (!raw) return null
  if (EXPIRE_AT_REGEX.test(raw)) return raw

  const match = raw.match(/^(\d{4})[-/](\d{2})[-/](\d{2})[ T](\d{2}):(\d{2})(?::\d{2})?$/)
  if (match) {
    return `${match[1]}/${match[2]}/${match[3]} ${match[4]}:${match[5]}`
  }

  const asNumber = Number(raw)
  if (Number.isFinite(asNumber) && asNumber > 0) {
    const date = new Date(asNumber)
    if (!Number.isNaN(date.getTime())) {
      return formatExpireAt(date)
    }
  }

  return null
}

const decodeJwtPayload = (token) => {
  const raw = String(token || '').trim()
  if (!raw) return null
  const parts = raw.split('.')
  if (parts.length < 2) return null
  const payload = parts[1]
  if (!payload) return null
  try {
    const padded = payload.replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(payload.length / 4) * 4, '=')
    const decoded = Buffer.from(padded, 'base64').toString('utf8')
    return JSON.parse(decoded)
  } catch {
    return null
  }
}

const deriveExpireAtFromToken = (token) => {
  const payload = decodeJwtPayload(token)
  if (!payload || typeof payload !== 'object') return null
  const exp = Number(payload.exp)
  if (!Number.isFinite(exp) || exp <= 0) return null
  const date = new Date(exp * 1000)
  if (Number.isNaN(date.getTime())) return null
  return formatExpireAt(date)
}

// 鐢熸垚闅忔満鍏戞崲鐮佺殑杈呭姪鍑芥暟
function generateRedemptionCode(length = 12) {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789' // 鎺掗櫎瀹规槗娣锋穯鐨勫瓧绗?
  let code = ''
  for (let i = 0; i < length; i++) {
    code += chars.charAt(Math.floor(Math.random() * chars.length))
    // 姣?浣嶆坊鍔犱竴涓垎闅旂
    if ((i + 1) % 4 === 0 && i < length - 1) {
      code += '-'
    }
  }
  return code
}

async function syncAccountAndCleanup(account) {
  let syncData = null
  const removedUsers = []

  try {
    console.log('[Auto Boarding] 鍑嗗鍚屾璐﹀彿:', {
      email: account.email,
      chatgptAccountId: account.chatgptAccountId
    })
    syncData = await syncAccountUserCount(account.id, {
      accountRecord: account
    })
    console.log('[Auto Boarding] 鍚屾瀹屾垚:', {
      email: account.email,
      syncedUserCount: syncData.syncedUserCount,
      fetchedUsers: syncData?.users?.items?.length || 0
    })
  } catch (syncError) {
    console.error('[Auto Boarding] 鍚屾澶辫触:', syncError)
    return {
      account,
      syncResult: null,
      removedUsers
    }
  }

  return {
    account: syncData?.account || account,
    syncResult: syncData
      ? {
        syncedUserCount: syncData.syncedUserCount,
        users: syncData.users
      }
      : null,
    removedUsers
  }
}

// 鑷姩涓婅溅鎺ュ彛
router.post('/', apiKeyAuth, async (req, res) => {
  try {
    const { email, token, refreshToken, chatgptAccountId, oaiDeviceId } = req.body
    const body = req.body || {}
    const hasOaiDeviceId = Object.prototype.hasOwnProperty.call(body, 'oaiDeviceId') || Object.prototype.hasOwnProperty.call(body, 'oai_device_id')
    const normalizedOaiDeviceId = String(oaiDeviceId ?? '').trim()
    const hasExpireAt = Object.prototype.hasOwnProperty.call(req.body || {}, 'expireAt')
    const expireAtInput = req.body?.expireAt
    const normalizedExpireAt = hasExpireAt ? normalizeExpireAt(expireAtInput) : null
	    const shouldUpdateExpireAt = hasExpireAt || Boolean(deriveExpireAtFromToken(token))
	    const derivedExpireAt = shouldUpdateExpireAt && !hasExpireAt ? deriveExpireAtFromToken(token) : null
	    const expireAt = hasExpireAt ? normalizedExpireAt : (derivedExpireAt || null)
	    // isDemoted/is_demoted: deprecated (ignored). Keep request compatibility.

    if (hasExpireAt && expireAtInput != null && String(expireAtInput).trim() && !normalizedExpireAt) {
      return res.status(400).json({
        error: 'Invalid expireAt format',
        message: 'expireAt 鏍煎紡閿欒锛岃浣跨敤 YYYY/MM/DD HH:mm'
      })
    }

    // 楠岃瘉蹇呭～瀛楁
    if (!email || !token) {
      return res.status(400).json({
        error: 'Email and token are required',
        message: '閭鍜孴oken鏄繀濉」'
      })
    }

    const normalizedEmail = normalizeEmail(email)

    const db = await getDatabase()

    // 妫€鏌ヨ处鍙锋槸鍚﹀凡瀛樺湪锛堥€氳繃email鎴朿hatgptAccountId锛?
    let existingAccount = null

    if (chatgptAccountId) {
      const result = db.exec(
        'SELECT id, email FROM gpt_accounts WHERE chatgpt_account_id = ?',
        [chatgptAccountId]
      )
      if (result.length > 0 && result[0].values.length > 0) {
        existingAccount = {
          id: result[0].values[0][0],
          email: result[0].values[0][1]
        }
      }
    }

    // 濡傛灉chatgptAccountId鏈壘鍒帮紝鍐嶉€氳繃email鏌ユ壘
    if (!existingAccount) {
      const result = db.exec(
        'SELECT id, email FROM gpt_accounts WHERE lower(email) = ?',
        [normalizedEmail]
      )
      if (result.length > 0 && result[0].values.length > 0) {
        existingAccount = {
          id: result[0].values[0][0],
          email: result[0].values[0][1]
        }
      }
    }

    if (existingAccount) {
      // 璐﹀彿宸插瓨鍦紝鏇存柊token鍜屽叾浠栦俊鎭?
	      db.run(
	        `UPDATE gpt_accounts
	         SET token = ?,
	             refresh_token = ?,
	             chatgpt_account_id = ?,
	             oai_device_id = CASE WHEN ? = 1 THEN ? ELSE oai_device_id END,
	             is_open = 1,
	             expire_at = CASE WHEN ? = 1 THEN ? ELSE expire_at END,
	             updated_at = DATETIME('now', 'localtime')
	         WHERE id = ?`,
	        [token, refreshToken || null, chatgptAccountId || null, hasOaiDeviceId && normalizedOaiDeviceId ? 1 : 0, normalizedOaiDeviceId || null, shouldUpdateExpireAt ? 1 : 0, expireAt, existingAccount.id]
	      )
	      saveDatabase()

	      // 鑾峰彇鏇存柊鍚庣殑璐﹀彿淇℃伅
	      const result = db.exec(`
	        SELECT id, email, token, refresh_token, user_count, chatgpt_account_id, oai_device_id, expire_at,
	               client_profile_key, client_user_agent, client_accept_language, client_oai_language,
	               created_at, updated_at
	        FROM gpt_accounts
	        WHERE id = ?
	      `, [existingAccount.id])

	      const row = result[0].values[0]
	      const account = {
	        id: row[0],
	        email: row[1],
	        token: row[2],
	        refreshToken: row[3],
	        userCount: row[4],
	        chatgptAccountId: row[5],
	        oaiDeviceId: row[6],
	        expireAt: row[7] || null,
	        clientProfileKey: row[8] || null,
	        clientUserAgent: row[9] || null,
	        clientAcceptLanguage: row[10] || null,
	        clientOaiLanguage: row[11] || null,
	        isDemoted: false,
	        createdAt: row[12],
	        updatedAt: row[13]
	      }

      const { account: syncedAccount, syncResult, removedUsers } = await syncAccountAndCleanup(account)

      return res.json({
        success: true,
        message: '账号信息已更新',
        action: 'updated',
        account: syncedAccount,
        syncResult,
        removedUsers
      })
    } else {
	      const generatedClientProfile = generateAccountClientProfile(normalizedEmail, normalizedOaiDeviceId)
	      // 鍒涘缓鏂拌处鍙凤紝榛樿浜烘暟璁剧疆涓?鑰屼笉鏄?
	      db.run(
	        `INSERT INTO gpt_accounts
	         (email, token, refresh_token, user_count, chatgpt_account_id, oai_device_id, expire_at, is_open, client_profile_key, client_user_agent, client_accept_language, client_oai_language, created_at, updated_at)
	         VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, DATETIME('now', 'localtime'), DATETIME('now', 'localtime'))`,
	        [
	          normalizedEmail,
	          token,
	          refreshToken || null,
	          1,
	          chatgptAccountId || null,
	          generatedClientProfile.oaiDeviceId,
	          expireAt,
	          generatedClientProfile.clientProfileKey,
	          generatedClientProfile.clientUserAgent,
	          generatedClientProfile.clientAcceptLanguage,
	          generatedClientProfile.clientOaiLanguage
	        ]
	      )

	      // 鑾峰彇鏂板垱寤虹殑璐﹀彿
	      const result = db.exec(`
	        SELECT id, email, token, refresh_token, user_count, chatgpt_account_id, oai_device_id, expire_at,
	               client_profile_key, client_user_agent, client_accept_language, client_oai_language,
	               created_at, updated_at
	        FROM gpt_accounts
	        WHERE id = last_insert_rowid()
	      `)

      const row = result[0].values[0]
	      const account = {
	        id: row[0],
	        email: row[1],
	        token: row[2],
	        refreshToken: row[3],
	        userCount: row[4],
	        chatgptAccountId: row[5],
	        oaiDeviceId: row[6],
	        expireAt: row[7] || null,
	        clientProfileKey: row[8] || null,
	        clientUserAgent: row[9] || null,
	        clientAcceptLanguage: row[10] || null,
	        clientOaiLanguage: row[11] || null,
	        isDemoted: false,
	        createdAt: row[12],
	        updatedAt: row[13]
	      }

      const generatedCodes = []

      saveDatabase()

      const { account: responseAccount, syncResult, removedUsers } = await syncAccountAndCleanup(account)

      return res.status(201).json({
        success: true,
        message: '自动上车成功，账号已添加到系统',
        action: 'created',
        account: responseAccount,
        generatedCodes,
        codesMessage: '新版本已取消账号创建时自动绑定兑换码',
        syncResult,
        removedUsers
      })
    }
  } catch (error) {
    console.error('Auto boarding error:', error)
    res.status(500).json({
      error: 'Internal server error',
      message: '服务器错误，请稍后重试'
    })
  }
})

// 鑾峰彇鑷姩涓婅溅缁熻淇℃伅锛堝彲閫夛級
router.get('/stats', apiKeyAuth, async (req, res) => {
  try {
    const db = await getDatabase()

    // 鑾峰彇鎬昏处鍙锋暟
    const totalResult = db.exec('SELECT COUNT(*) as count FROM gpt_accounts')
    const total = totalResult[0]?.values[0]?.[0] || 0

    // 鑾峰彇鏈€杩?4灏忔椂鏂板鐨勮处鍙锋暟
    const recentResult = db.exec(`
      SELECT COUNT(*) as count
      FROM gpt_accounts
      WHERE created_at >= datetime('now', 'localtime', '-1 day')
    `)
    const recent = recentResult[0]?.values[0]?.[0] || 0

    res.json({
      success: true,
      stats: {
        totalAccounts: total,
        recentAccounts: recent
      }
    })
  } catch (error) {
    console.error('Get stats error:', error)
    res.status(500).json({
      error: 'Internal server error',
      message: '鑾峰彇缁熻淇℃伅澶辫触'
    })
  }
})

export default router

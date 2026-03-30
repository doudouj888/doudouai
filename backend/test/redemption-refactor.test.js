import test from 'node:test'
import assert from 'node:assert/strict'
import initSqlJs from 'sql.js'

import { countAvailableRecoveryCodes, selectRecoveryCode } from '../src/services/account-recovery.js'
import { ensureOpenAccountsOrderCode, reserveOpenAccountsCode } from '../src/services/open-accounts-redemption.js'

const createDb = async () => {
  const SQL = await initSqlJs()
  const db = new SQL.Database()

  db.run(`
    CREATE TABLE channels (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      key TEXT,
      name TEXT,
      redeem_mode TEXT,
      is_active INTEGER DEFAULT 1
    );

    CREATE TABLE redemption_codes (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      code TEXT,
      account_email TEXT,
      is_redeemed INTEGER DEFAULT 0,
      redeemed_at TEXT,
      redeemed_by TEXT,
      channel TEXT DEFAULT 'common',
      channel_name TEXT,
      created_at TEXT,
      updated_at TEXT,
      reserved_for_uid TEXT,
      reserved_for_username TEXT,
      reserved_for_entry_id INTEGER,
      reserved_at TEXT,
      reserved_for_order_no TEXT,
      reserved_for_order_email TEXT,
      order_type TEXT,
      status TEXT DEFAULT 'unused',
      assigned_account_id INTEGER,
      activated_email TEXT,
      activated_at TEXT,
      is_downstream_sold INTEGER DEFAULT 0,
      downstream_sold_at TEXT,
      fulfillment_mode TEXT DEFAULT 'internal_invite',
      supplier_name TEXT,
      supplier_type TEXT,
      supplier_request_id TEXT,
      supplier_status TEXT,
      supplier_response_code TEXT,
      supplier_response_message TEXT,
      supplier_redeemed_at TEXT,
      processing_token TEXT,
      processing_started_at TEXT,
      last_error TEXT,
      prefix TEXT,
      batch_no TEXT
    );

    CREATE TABLE credit_orders (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      order_no TEXT,
      code_id INTEGER,
      code TEXT,
      code_account_email TEXT,
      updated_at TEXT
    );
  `)

  db.run(
    `INSERT INTO channels (key, name, redeem_mode, is_active) VALUES
      ('common', '通用渠道', 'code', 1),
      ('linux-do', 'Linux DO', 'code', 1),
      ('xhs', '小红书', 'external-card', 1)`
  )

  return db
}

const scalar = (db, sql, params = []) => db.exec(sql, params)?.[0]?.values?.[0]?.[0]

test('countAvailableRecoveryCodes counts generic unused common codes without account binding', async () => {
  const db = await createDb()

  db.run(
    `INSERT INTO redemption_codes
      (code, account_email, is_redeemed, channel, created_at, updated_at, status, is_downstream_sold, fulfillment_mode)
     VALUES
      ('FREE-CODE-001', NULL, 0, 'common', DATETIME('now', 'localtime'), DATETIME('now', 'localtime'), 'unused', 0, 'internal_invite'),
      ('USED-CODE-001', NULL, 1, 'common', DATETIME('now', 'localtime'), DATETIME('now', 'localtime'), 'used', 0, 'internal_invite'),
      ('PROC-CODE-001', NULL, 0, 'common', DATETIME('now', 'localtime'), DATETIME('now', 'localtime'), 'processing', 0, 'internal_invite'),
      ('DOWN-CODE-001', NULL, 0, 'common', DATETIME('now', 'localtime'), DATETIME('now', 'localtime'), 'unused', 1, 'internal_invite'),
      ('EXTA-CODE-001', NULL, 0, 'common', DATETIME('now', 'localtime'), DATETIME('now', 'localtime'), 'unused', 0, 'external_api'),
      ('XHS-CODE-001', NULL, 0, 'xhs', DATETIME('now', 'localtime'), DATETIME('now', 'localtime'), 'unused', 0, 'internal_invite'),
      ('RSV-CODE-001', NULL, 0, 'common', DATETIME('now', 'localtime'), DATETIME('now', 'localtime'), 'unused', 0, 'internal_invite')`
  )
  db.run(`UPDATE redemption_codes SET reserved_for_order_no = 'ORD-1' WHERE code = 'RSV-CODE-001'`)

  const availableCount = countAvailableRecoveryCodes(db, {
    codeCreatedWithinDays: 7,
    channel: 'common'
  })

  assert.equal(availableCount, 1)
})

test('selectRecoveryCode can return unbound codes and prefers non-today candidates', async () => {
  const db = await createDb()

  db.run(
    `INSERT INTO redemption_codes
      (code, account_email, is_redeemed, channel, created_at, updated_at, status, is_downstream_sold, fulfillment_mode)
     VALUES
      ('TODAY-CODE-001', NULL, 0, 'common', DATETIME('now', 'localtime'), DATETIME('now', 'localtime'), 'unused', 0, 'internal_invite'),
      ('OLDER-CODE-001', NULL, 0, 'common', DATETIME('now', 'localtime', '-1 day'), DATETIME('now', 'localtime', '-1 day'), 'unused', 0, 'internal_invite'),
      ('OLDER-CODE-002', 'skip@example.com', 0, 'common', DATETIME('now', 'localtime', '-2 day'), DATETIME('now', 'localtime', '-2 day'), 'unused', 0, 'internal_invite')`
  )

  const selected = selectRecoveryCode(db, {
    minExpireMs: Date.now(),
    preferNonToday: true,
    codeCreatedWithinDays: 7,
    excludeAccountEmails: ['skip@example.com']
  })

  assert.ok(selected)
  assert.equal(selected.recoveryCode, 'OLDER-CODE-001')
  assert.equal(selected.recoveryAccountEmail, '')
})

test('open accounts reservation works with unbound unused codes and persists on order', async () => {
  const db = await createDb()

  db.run(
    `INSERT INTO credit_orders (order_no, updated_at) VALUES ('ORDER-1001', DATETIME('now', 'localtime'))`
  )
  db.run(
    `INSERT INTO redemption_codes
      (code, account_email, is_redeemed, redeemed_by, channel, created_at, updated_at, status, is_downstream_sold)
     VALUES
      ('LINUX-USED-001', NULL, 1, 'used@example.com', 'linux-do', DATETIME('now', 'localtime', '-2 day'), DATETIME('now', 'localtime', '-2 day'), 'used', 0),
      ('LINUX-FREE-001', NULL, 0, NULL, 'linux-do', DATETIME('now', 'localtime', '-1 day'), DATETIME('now', 'localtime', '-1 day'), 'unused', 0)`
  )

  const reserved = reserveOpenAccountsCode(db, {
    orderNo: 'ORDER-1001',
    email: 'buyer@example.com'
  })

  assert.ok(reserved)
  assert.equal(reserved.code, 'LINUX-FREE-001')
  assert.equal(reserved.accountEmail, '')
  assert.equal(
    scalar(db, `SELECT reserved_for_order_no FROM redemption_codes WHERE code = 'LINUX-FREE-001'`),
    'ORDER-1001'
  )

  const ensured = ensureOpenAccountsOrderCode(db, {
    orderNo: 'ORDER-1001',
    email: 'buyer@example.com'
  })

  assert.ok(ensured)
  assert.equal(ensured.code, 'LINUX-FREE-001')
  assert.equal(
    scalar(db, `SELECT code FROM credit_orders WHERE order_no = 'ORDER-1001'`),
    'LINUX-FREE-001'
  )
})

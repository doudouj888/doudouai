import crypto from 'crypto'

export const REDEMPTION_CODE_SEGMENT_LENGTH = 4
export const REDEMPTION_CODE_SEGMENT_COUNT = 3
export const REDEMPTION_CODE_RAW_LENGTH = REDEMPTION_CODE_SEGMENT_LENGTH * REDEMPTION_CODE_SEGMENT_COUNT
export const REDEMPTION_CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
export const REDEMPTION_CODE_REGEX = /^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$/

export const stripRedemptionCode = (value) => (
  String(value ?? '')
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]/g, '')
    .slice(0, REDEMPTION_CODE_RAW_LENGTH)
)

const formatCodeSegments = (raw) => String(raw || '').match(/.{1,4}/g)?.join('-') || ''

export const formatPartialRedemptionCode = (value) => formatCodeSegments(stripRedemptionCode(value))

export const normalizeRedemptionCode = (value) => {
  const raw = stripRedemptionCode(value)
  if (raw.length !== REDEMPTION_CODE_RAW_LENGTH) return ''
  return formatCodeSegments(raw)
}

export const isValidRedemptionCode = (value) => REDEMPTION_CODE_REGEX.test(normalizeRedemptionCode(value))

export const generateRedemptionCode = () => {
  const bytes = crypto.randomBytes(REDEMPTION_CODE_RAW_LENGTH)
  let raw = ''

  for (let index = 0; index < REDEMPTION_CODE_RAW_LENGTH; index += 1) {
    raw += REDEMPTION_CODE_ALPHABET[bytes[index] % REDEMPTION_CODE_ALPHABET.length]
  }

  return formatCodeSegments(raw)
}

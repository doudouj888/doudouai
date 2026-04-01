export const REDEMPTION_CODE_SEGMENT_LENGTH = 4
export const REDEMPTION_CODE_SEGMENT_COUNT = 3
export const REDEMPTION_CODE_RAW_LENGTH = REDEMPTION_CODE_SEGMENT_LENGTH * REDEMPTION_CODE_SEGMENT_COUNT
export const REDEMPTION_CODE_REGEX = /^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$/

const stripRedemptionCode = (value: string) => (
  String(value ?? '')
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]/g, '')
    .slice(0, REDEMPTION_CODE_RAW_LENGTH)
)

const formatCodeSegments = (raw: string) => raw.match(/.{1,4}/g)?.join('-') || ''

export const formatPartialRedemptionCode = (value: string) => formatCodeSegments(stripRedemptionCode(value))

export const normalizeRedemptionCode = (value: string) => {
  const raw = stripRedemptionCode(value)
  if (raw.length !== REDEMPTION_CODE_RAW_LENGTH) return ''
  return formatCodeSegments(raw)
}

export const isValidRedemptionCode = (value: string) => REDEMPTION_CODE_REGEX.test(normalizeRedemptionCode(value))

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, nextTick, watch } from 'vue'
import { authService, userService, adminService, versionService, purchaseService } from '@/services/api'
import type { AdminProxyTestResult, VersionInfo, LatestVersionInfo, Channel, PurchaseProduct, PurchaseMeta, PurchaseOrderType } from '@/services/api'
import { useAppConfigStore } from '@/stores/appConfig'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import AnnouncementAdminPanel from '@/components/AnnouncementAdminPanel.vue'
import InfoTooltip from '@/components/InfoTooltip.vue'
import { Eye, EyeOff, Sparkles, KeyRound, AlertCircle, CheckCircle2, RefreshCw, Settings, CreditCard, Link, Mail, Shield, Plus, Trash2 } from 'lucide-vue-next'

const teleportReady = ref(false)
const activeTab = ref<'settings' | 'announcements'>('settings')
type SettingsModuleId = 'general' | 'billing' | 'integrations' | 'upstream' | 'notifications' | 'security'
type SettingsResourceKey =
  | 'apiKey'
  | 'featureFlags'
  | 'teamCapacity'
  | 'accountRecovery'
  | 'channels'
  | 'purchaseProducts'
  | 'downstreamSale'
  | 'emailWhitelist'
  | 'pointsWithdraw'
  | 'smtp'
  | 'linuxdoOauth'
  | 'linuxdoCredit'
  | 'zpay'
  | 'turnstile'
  | 'telegram'
  | 'proxy'
  | 'upstream'

const settingsSubTab = ref<SettingsModuleId>('general')

const settingsNav = [
  { id: 'general', label: '基础设置', desc: '功能开关、白名单与团队容量', icon: Settings },
  { id: 'billing', label: '支付与财务', desc: '商品、支付渠道与提现相关设置', icon: CreditCard },
  { id: 'integrations', label: '集成配置', desc: 'OAuth、第三方接入与通知渠道', icon: Link },
  { id: 'upstream', label: '上下游接口', desc: '上游供应与下游对接配置', icon: RefreshCw },
  { id: 'notifications', label: '通知设置', desc: 'SMTP 与 Telegram 通知配置', icon: Mail },
  { id: 'security', label: '安全设置', desc: 'API 密钥与访问控制', icon: Shield },
] as const

const activeNavItem = computed(() => settingsNav.find(n => n.id === settingsSubTab.value))
const settingsResourceLoaded = ref<Record<SettingsResourceKey, boolean>>({
  apiKey: false,
  featureFlags: false,
  teamCapacity: false,
  accountRecovery: false,
  channels: false,
  purchaseProducts: false,
  downstreamSale: false,
  emailWhitelist: false,
  pointsWithdraw: false,
  smtp: false,
  linuxdoOauth: false,
  linuxdoCredit: false,
  zpay: false,
  turnstile: false,
  telegram: false,
  proxy: false,
  upstream: false,
})
const settingsResourcePromises = new Map<SettingsResourceKey, Promise<void>>()

// çæ¬æ£æ¥ç¸å
?
const versionLoading = ref(false)
const versionDialogOpen = ref(false)
const currentVersion = ref<VersionInfo | null>(null)
const latestVersion = ref<LatestVersionInfo | null>(null)
const versionError = ref('')

const hasNewVersion = computed(() => {
  if (!currentVersion.value || !latestVersion.value) return false
  return currentVersion.value.version !== latestVersion.value.version
})

const checkForUpdates = async () => {
  versionLoading.value = true
  versionError.value = ''
  currentVersion.value = null
  latestVersion.value = null

  try {
    const [current, latest] = await Promise.all([
      versionService.getVersion(),
      versionService.getLatest().catch(err => {
        if (err.response?.status === 404) {
          return null
        }
        throw err
      })
    ])
    currentVersion.value = current
    latestVersion.value = latest
    versionDialogOpen.value = true
  } catch (err: any) {
    versionError.value = err.response?.data?.error || 'æ£æ¥æ´æ°å¤±è´?
    versionDialogOpen.value = true
  } finally {
    versionLoading.value = false
  }
}

// APIå¯é¥ç¸å
³
const apiKey = ref('')
const apiKeyError = ref('')
const apiKeySuccess = ref('')
const apiKeyLoading = ref(false)
const showApiKey = ref(false) // æ§å¶æ¾ç¤º/éèAPIå¯é¥

const isSuperAdmin = computed(() => {
  const user = authService.getCurrentUser()
  return Array.isArray(user?.roles) && user.roles.includes('super_admin')
})

const appConfigStore = useAppConfigStore()

// åè½å¼å
³ï¼ä»
è¶
çº§ç®¡çåï¼?
const featureFlags = ref({
  xhs: true,
  xianyu: true,
  payment: true,
  openAccounts: true
})
const featureFlagsError = ref('')
const featureFlagsSuccess = ref('')
const featureFlagsLoading = ref(false)

const teamCapacityLimit = ref('5')
const teamCapacityError = ref('')
const teamCapacitySuccess = ref('')
const teamCapacityLoading = ref(false)

// è¡¥å½è®¾ç½®ï¼ä»
è¶
çº§ç®¡çåï¼
const accountRecoveryForceTodayCodes = ref(false)
const accountRecoveryCodeWindowDays = ref('7')
const accountRecoveryRequireExpireCoverDeadline = ref(false)
const accountRecoverySettingsError = ref('')
const accountRecoverySettingsSuccess = ref('')
const accountRecoverySettingsLoading = ref(false)

// æ¸ éç®¡çï¼ä»
è¶
çº§ç®¡çåï¼
const channels = ref<Channel[]>([])
const channelsLoading = ref(false)
const channelsError = ref('')
const channelsSuccess = ref('')
const channelDialogOpen = ref(false)
const channelDialogMode = ref<'create' | 'edit'>('create')
const channelFormKey = ref('')
const channelFormName = ref('')
const channelFormRedeemMode = ref('code')
const channelFormProviderType = ref('local')
const channelFormAllowFallback = ref(false)
const channelFormAllowDownstreamSale = ref(false)
const channelFormIsActive = ref(true)
const channelFormSortOrder = ref('0')
const channelRedeemModeOptions = [
  { value: 'code', label: 'ç«å
å
æ¢ç ? },
  { value: 'linux-do', label: 'Linux DO' },
  { value: 'xhs', label: 'å°çº¢ä¹? },
  { value: 'xianyu', label: 'é²é±¼' },
  { value: 'external-card', label: 'ä¸æ¸¸å¡å¯' }
]
const channelProviderTypeOptions = [
  { value: 'local', label: 'æ¬å°å±¥çº¦' },
  { value: 'custom-http', label: 'èªå®ä¹æ¥å? },
  { value: 'platform-upstream', label: 'å¹³å°éç¨æ¥å£' }
]
const channelFormProviderOptions = computed(() => (
  channelFormRedeemMode.value === 'external-card'
    ? channelProviderTypeOptions.filter(option => option.value !== 'local')
    : channelProviderTypeOptions.filter(option => option.value === 'local')
))

// æ¯ä»ååç®¡çï¼ä»
è¶
çº§ç®¡çåï¼
const purchaseProducts = ref<PurchaseProduct[]>([])
const purchaseProductsLoading = ref(false)
const purchaseProductsError = ref('')
const purchaseProductsSuccess = ref('')
const purchaseProductDialogOpen = ref(false)
const purchaseProductDialogMode = ref<'create' | 'edit'>('create')
const purchaseProductFormKey = ref('')
const purchaseProductFormName = ref('')
const purchaseProductFormAmount = ref('')
const purchaseProductFormServiceDays = ref('30')
const purchaseProductFormOrderType = ref<PurchaseOrderType>('warranty')
const purchaseProductFormCodeChannels = ref('')
const purchaseProductFormIsActive = ref(true)
const purchaseProductFormSortOrder = ref('0')
const purchaseAvailability = ref<Record<string, number>>({})

// é®ç®±åç¼ç½åå?
const emailDomainWhitelist = ref('')
const emailDomainWhitelistError = ref('')
const emailDomainWhitelistSuccess = ref('')
const emailDomainWhitelistLoading = ref(false)

// ç§¯åæç°è®¾ç½®ï¼ä»
è¶
çº§ç®¡çåï¼
const pointsWithdrawRatePoints = ref('1')
const pointsWithdrawRateCashYuan = ref('1.00')
const pointsWithdrawMinCashYuan = ref('10.00')
const pointsWithdrawMinPoints = ref<number | null>(null)
const pointsWithdrawStepPoints = ref<number | null>(null)
const pointsWithdrawError = ref('')
const pointsWithdrawSuccess = ref('')
const pointsWithdrawLoading = ref(false)

// SMTP é®ä»¶åè­¦é
ç½®ï¼ä»
è¶
çº§ç®¡çåï¼
const smtpHost = ref('')
const smtpPort = ref('465')
const smtpSecure = ref<'true' | 'false'>('true')
const smtpUser = ref('')
const smtpPass = ref('')
const smtpPassSet = ref(false)
const smtpPassStored = ref(false)
const smtpFrom = ref('')
const adminAlertEmail = ref('')
const smtpError = ref('')
const smtpSuccess = ref('')
const smtpLoading = ref(false)
const showSmtpPass = ref(false)

// Linux DO OAuth é
ç½®ï¼ä»
è¶
çº§ç®¡çåï¼
const linuxdoClientId = ref('')
const linuxdoClientSecret = ref('')
const linuxdoRedirectUri = ref('')
const linuxdoClientSecretSet = ref(false)
const linuxdoClientSecretStored = ref(false)
const linuxdoOauthError = ref('')
const linuxdoOauthSuccess = ref('')
const linuxdoOauthLoading = ref(false)
const showLinuxdoClientSecret = ref(false)

// Linux DO Credit é
ç½®ï¼ä»
è¶
çº§ç®¡çåï¼
const linuxdoCreditPid = ref('')
const linuxdoCreditKey = ref('')
const linuxdoCreditKeySet = ref(false)
const linuxdoCreditKeyStored = ref(false)
const linuxdoCreditError = ref('')
const linuxdoCreditSuccess = ref('')
const linuxdoCreditLoading = ref(false)
const showLinuxdoCreditKey = ref(false)

// ZPAY æ¯ä»é
ç½®ï¼ä»
è¶
çº§ç®¡çåï¼
const zpayBaseUrl = ref('https://zpayz.cn')
const zpayPid = ref('')
const zpayKey = ref('')
const zpayKeySet = ref(false)
const zpayKeyStored = ref(false)
const zpayError = ref('')
const zpaySuccess = ref('')
const zpayLoading = ref(false)
const showZpayKey = ref(false)

// ä¸æ¸¸å®ç é
ç½®ï¼ä»
è¶
çº§ç®¡çåï¼
const downstreamSaleEnabled = ref(false)
const downstreamSaleProductName = ref('')
const downstreamSaleAmount = ref('9.90')
const downstreamSalePayAlipayEnabled = ref(true)
const downstreamSalePayWxpayEnabled = ref(false)
const downstreamSaleError = ref('')
const downstreamSaleSuccess = ref('')
const downstreamSaleLoading = ref(false)

// Cloudflare Turnstile é
ç½®ï¼ä»
è¶
çº§ç®¡çåï¼
const turnstileSiteKey = ref('')
const turnstileSecretKey = ref('')
const turnstileEnabled = ref(false)
const turnstileSecretSet = ref(false)
const turnstileSecretStored = ref(false)
const turnstileSiteKeyStored = ref(false)
const turnstileError = ref('')
const turnstileSuccess = ref('')
const turnstileLoading = ref(false)
const showTurnstileSecretKey = ref(false)

// Telegram Bot é
ç½®ï¼ä»
è¶
çº§ç®¡çåï¼
const telegramAllowedUserIds = ref('')
const telegramAllowedUserIdsStored = ref(false)
const telegramBotToken = ref('')
const telegramTokenSet = ref(false)
const telegramTokenStored = ref(false)
const telegramNotifyEnabled = ref<'true' | 'false'>('true')
const telegramNotifyEnabledStored = ref(false)
const telegramNotifyChatIds = ref('')
const telegramNotifyChatIdsStored = ref(false)
const telegramNotifyTimeoutMs = ref('8000')
const telegramNotifyTimeoutMsStored = ref(false)
const telegramError = ref('')
const telegramSuccess = ref('')
const telegramLoading = ref(false)
const showTelegramBotToken = ref(false)

// å
¨å±ä»£çé
ç½®ï¼ä»
è¶
çº§ç®¡çåï¼
type ProxyRow = {
  id: string
  value: string
}

const createProxyRow = (value: string = ''): ProxyRow => ({
  id: `${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`,
  value,
})

const proxyStored = ref(false)
const proxyEffectiveCount = ref(0)
const proxyError = ref('')
const proxySuccess = ref('')
const proxyLoading = ref(false)
const proxyTesting = ref(false)
const proxyTestTotal = ref(0)
const proxyTestPassed = ref(0)
const proxyTestFailed = ref(0)
const proxyTestResults = ref<AdminProxyTestResult[]>([])
const proxyRows = ref<ProxyRow[]>([createProxyRow()])
const proxyLastTestedProxyUrls = ref('')
const parseProxyEntries = (value?: string | null) => (
  String(value || '')
    .split(/[
,;]+/g)
    .map(item => item.trim())
    .filter(Boolean)
)
const buildProxyLookupKeys = (value?: string | null) => {
  const raw = String(value || '').trim()
  if (!raw) return []
  const keys = new Set<string>([raw])
  try {
    const parsed = new URL(raw)
    const protocol = String(parsed.protocol || '').replace(':', '').toLowerCase()
    const auth = parsed.username
      ? `${parsed.username}${parsed.password ? `:${parsed.password}` : ''}@`
      : ''
    const host = (parsed.hostname || '').toLowerCase()
    const port = parsed.port ? `:${parsed.port}` : ''
    const pathname = parsed.pathname && parsed.pathname !== '/' ? parsed.pathname : ''
    const search = parsed.search || ''
    const hash = parsed.hash || ''
    keys.add(`${protocol}://${auth}${host}${port}${pathname}${search}${hash}`)
    keys.add(`${protocol}://${host}${port}${pathname}${search}${hash}`)
    keys.add(`${protocol}://${host}${port}`)
  } catch {
    return Array.from(keys)
  }
  return Array.from(keys)
}
const setProxyRowsFromText = (value?: string | null) => {
  const entries = parseProxyEntries(value)
  proxyRows.value = entries.length > 0
    ? entries.map(entry => createProxyRow(entry))
    : [createProxyRow()]
}
const proxyDraftProxyUrls = computed(() => (
  proxyRows.value
    .map(row => row.value.trim())
    .filter(Boolean)
    .join('
')
))
const proxyDraftCount = computed(() => (
  proxyRows.value.filter(row => row.value.trim()).length
))
const proxyResultLookup = computed(() => {
  const lookup = new Map<string, AdminProxyTestResult>()
  for (const result of proxyTestResults.value) {
    for (const key of buildProxyLookupKeys(result.proxy)) {
      lookup.set(key, result)
    }
  }
  return lookup
})
const getProxyRowResult = (value?: string | null) => {
  for (const key of buildProxyLookupKeys(value)) {
    const result = proxyResultLookup.value.get(key)
    if (result) return result
  }
  return null
}
const resetProxyTestState = () => {
  proxyTestTotal.value = 0
  proxyTestPassed.value = 0
  proxyTestFailed.value = 0
  proxyTestResults.value = []
  proxyLastTestedProxyUrls.value = ''
}
const addProxyRow = () => {
  proxyRows.value = [...proxyRows.value, createProxyRow()]
}
const removeProxyRow = (index: number) => {
  if (proxyRows.value.length <= 1) {
    proxyRows.value = [createProxyRow()]
    return
  }
  proxyRows.value = proxyRows.value.filter((_, currentIndex) => currentIndex !== index)
}

watch(proxyDraftProxyUrls, (next, previous) => {
  if (next === previous) return
  if (next !== proxyLastTestedProxyUrls.value) {
    resetProxyTestState()
  }
})

// ä¸æ¸¸å±¥çº¦é
ç½®ï¼ä»
è¶
çº§ç®¡çåï¼
type UpstreamInboundClientRow = {
  id: string
  domain: string
  apiKey: string
  apiKeySet: boolean
  apiKeyStored: boolean
  legacy: boolean
  showApiKey: boolean
}

const DEFAULT_UPSTREAM_CUSTOM_BODY_TEMPLATE = JSON.stringify({
  userEmail: '{{email}}',
  cardCode: '{{code}}'
}, null, 2)
const upstreamConfigTab = ref<'outbound' | 'inbound'>('outbound')
const upstreamProviderEnabled = ref<'true' | 'false'>('false')
const upstreamProviderType = ref('custom-http')
const upstreamSupplierName = ref('')
const upstreamBaseUrl = ref('')
const upstreamCustomUrl = ref('')
const upstreamCustomBodyTemplate = ref(DEFAULT_UPSTREAM_CUSTOM_BODY_TEMPLATE)
const upstreamTimeoutMs = ref('15000')
const upstreamOutboundApiKey = ref('')
const upstreamOutboundApiKeySet = ref(false)
const upstreamOutboundApiKeyStored = ref(false)
const upstreamApiEnabled = ref<'true' | 'false'>('false')
const upstreamPublicBaseUrl = ref('')
const upstreamPublicBaseUrlStored = ref(false)
const createUpstreamInboundClientRow = (overrides: Partial<UpstreamInboundClientRow> = {}): UpstreamInboundClientRow => ({
  id: '',
  domain: '',
  apiKey: '',
  apiKeySet: false,
  apiKeyStored: false,
  legacy: false,
  showApiKey: false,
  ...overrides,
})
const upstreamInboundClients = ref<UpstreamInboundClientRow[]>([createUpstreamInboundClientRow()])
const upstreamError = ref('')
const upstreamSuccess = ref('')
const upstreamLoading = ref(false)
const showUpstreamOutboundApiKey = ref(false)
const isCustomUpstreamProvider = computed(() => upstreamProviderType.value === 'custom-http')
const isPlatformUpstreamProvider = computed(() => upstreamProviderType.value === 'platform-upstream')
const upstreamPlaceholderHelp = 'æ¯æ {{email}}ã{{code}}ã{{channel}} ä¸ä¸ªå ä½ç¬¦ã?
const normalizeUpstreamProviderValue = (value?: string | null) => (
  value === 'platform-upstream' ? 'platform-upstream' : 'custom-http'
)
const normalizeUpstreamInboundDomain = (value?: string | null) => {
  const raw = String(value || '').trim().toLowerCase()
  if (!raw || raw === '*' || raw === 'default') return ''
  const candidate = /^[a-z][a-z0-9+.-]*:\/\//i.test(raw) ? raw : `https://${raw}`
  try {
    return new URL(candidate).hostname.trim().toLowerCase().replace(/\.+$/, '')
  } catch {
    return ''
  }
}
const normalizeChannelProviderValue = (value?: string | null) => (
  value === 'platform-upstream' ? 'platform-upstream' : (value === 'local' ? 'local' : 'custom-http')
)

onMounted(async () => {
  await nextTick()
  teleportReady.value = !!document.getElementById('header-actions')
})

onUnmounted(() => {
  teleportReady.value = false
})

const loadApiKey = async () => {
  try {
    const response = await userService.getApiKey()
    apiKey.value = typeof response.apiKey === 'string' ? response.apiKey : ''
  } catch (err: any) {
    console.error('Load API key error:', err)
  }
}

const loadFeatureFlags = async () => {
  featureFlagsError.value = ''
  featureFlagsSuccess.value = ''
  try {
    const response = await adminService.getFeatureFlags()
    const next = response.features || {}
    featureFlags.value = {
      xhs: next.xhs !== false,
      xianyu: next.xianyu !== false,
      payment: next.payment !== false,
      openAccounts: next.openAccounts !== false
    }
    appConfigStore.features = { ...featureFlags.value }
  } catch (err: any) {
    featureFlagsError.value = err.response?.data?.error || 'å è½½åè½å¼å
³å¤±è´?
  }
}

const saveFeatureFlags = async () => {
  featureFlagsError.value = ''
  featureFlagsSuccess.value = ''
  featureFlagsLoading.value = true
  try {
    const response = await adminService.updateFeatureFlags({
      features: { ...featureFlags.value }
    })
    const next = response.features || {}
    featureFlags.value = {
      xhs: next.xhs !== false,
      xianyu: next.xianyu !== false,
      payment: next.payment !== false,
      openAccounts: next.openAccounts !== false
    }
    appConfigStore.features = { ...featureFlags.value }
    featureFlagsSuccess.value = 'å·²ä¿å­?
    setTimeout(() => (featureFlagsSuccess.value = ''), 3000)
  } catch (err: any) {
    featureFlagsError.value = err.response?.data?.error || 'ä¿å­å¤±è´¥'
  } finally {
    featureFlagsLoading.value = false
    teamCapacitySuccess.value = '已保存 Team 容量设置'
}

    teamCapacityError.value = err.response?.data?.error || '保存失败'
  if (!next) {
    accountRecoveryRequireExpireCoverDeadline.value = false
  }
  if (!accountRecoveryCodeWindowDays.value.trim()) {
    accountRecoveryCodeWindowDays.value = '7'
  }
})

watch(channelFormRedeemMode, (next) => {
  if (next === 'external-card') {
    if (channelFormProviderType.value === 'local') {
      channelFormProviderType.value = 'platform-upstream'
    }
    return
  }
  channelFormProviderType.value = 'local'
})

const loadTeamCapacitySettings = async () => {
  teamCapacityError.value = ''
  teamCapacitySuccess.value = ''
  try {
    const response = await adminService.getTeamCapacitySettings()
    teamCapacityLimit.value = String(response.settings?.teamCapacityLimit ?? 5)
  } catch (err: any) {
    teamCapacityError.value = err.response?.data?.error || 'å è½½ Team å®¹éè®¾ç½®å¤±è´¥'
  }
}

const saveTeamCapacitySettings = async () => {
  teamCapacityError.value = ''
  teamCapacitySuccess.value = ''
  teamCapacityLoading.value = true
  try {
    const parsedValue = Number.parseInt(teamCapacityLimit.value, 10)
    if (!Number.isFinite(parsedValue) || parsedValue <= 0 || parsedValue > 999) {
      teamCapacityError.value = 'Please enter a valid seat limit between 1 and 999'
      return
    }
    const response = await adminService.updateTeamCapacitySettings({
      settings: {
        teamCapacityLimit: parsedValue
      }
    })
    teamCapacityLimit.value = String(response.settings?.teamCapacityLimit ?? parsedValue)
    teamCapacitySuccess.value = '已保存 Team 容量设置'
    setTimeout(() => (teamCapacitySuccess.value = ''), 3000)
  } catch (err: any) {
    teamCapacityError.value = err.response?.data?.error || '保存失败'
  } finally {
    teamCapacityLoading.value = false
  }
}

const loadAccountRecoverySettings = async () => {
  accountRecoverySettingsError.value = ''
  accountRecoverySettingsSuccess.value = ''
  try {
    const response = await adminService.getAccountRecoverySettings()
    const next = response.settings || ({} as any)
    accountRecoveryForceTodayCodes.value = Boolean(next.forceTodayCodes)
    accountRecoveryCodeWindowDays.value = String(next.codeWindowDays ?? 7)
    accountRecoveryRequireExpireCoverDeadline.value = Boolean(next.requireExpireCoverDeadline)
    if (!accountRecoveryForceTodayCodes.value) {
      accountRecoveryRequireExpireCoverDeadline.value = false
    }
  } catch (err: any) {
    accountRecoverySettingsError.value = err.response?.data?.error || 'å è½½è¡¥å½è®¾ç½®å¤±è´¥'
  }
}

const saveAccountRecoverySettings = async () => {
  accountRecoverySettingsError.value = ''
  accountRecoverySettingsSuccess.value = ''
  accountRecoverySettingsLoading.value = true
  try {
    const parsedDays = Number.parseInt(accountRecoveryCodeWindowDays.value, 10)
    const codeWindowDays = Number.isFinite(parsedDays) ? Math.max(1, Math.min(365, parsedDays)) : 7
    const settingsPayload = {
      forceTodayCodes: accountRecoveryForceTodayCodes.value,
      codeWindowDays,
      requireExpireCoverDeadline: accountRecoveryForceTodayCodes.value ? accountRecoveryRequireExpireCoverDeadline.value : false
    }
    const response = await adminService.updateAccountRecoverySettings({ settings: settingsPayload })
    const next = response.settings || ({} as any)
    accountRecoveryForceTodayCodes.value = Boolean(next.forceTodayCodes)
    accountRecoveryCodeWindowDays.value = String(next.codeWindowDays ?? 7)
    accountRecoveryRequireExpireCoverDeadline.value = Boolean(next.requireExpireCoverDeadline)
    if (!accountRecoveryForceTodayCodes.value) {
      accountRecoveryRequireExpireCoverDeadline.value = false
    }
    accountRecoverySettingsSuccess.value = 'å·²ä¿å­?
    setTimeout(() => (accountRecoverySettingsSuccess.value = ''), 3000)
  } catch (err: any) {
    accountRecoverySettingsError.value = err.response?.data?.error || 'ä¿å­å¤±è´¥'
  } finally {
    accountRecoverySettingsLoading.value = false
  }
}

const loadChannels = async () => {
  if (channelsLoading.value) return
  channelsLoading.value = true
  channelsError.value = ''
  channelsSuccess.value = ''
  try {
    const response = await adminService.getChannels()
    channels.value = Array.isArray(response.channels) ? response.channels : []
  } catch (err: any) {
    channelsError.value = err.response?.data?.error || 'å è½½æ¸ éå¤±è´¥'
  } finally {
    channelsLoading.value = false
  }
}

const openCreateChannelDialog = () => {
  channelDialogMode.value = 'create'
  channelFormKey.value = ''
  channelFormName.value = ''
  channelFormRedeemMode.value = 'code'
  channelFormProviderType.value = 'local'
  channelFormAllowFallback.value = false
  channelFormAllowDownstreamSale.value = false
  channelFormIsActive.value = true
  channelFormSortOrder.value = '0'
  channelDialogOpen.value = true
}

const openEditChannelDialog = (channel: Channel) => {
  channelDialogMode.value = 'edit'
  channelFormKey.value = channel.key
  channelFormName.value = channel.name
  channelFormRedeemMode.value = channel.redeemMode === 'api' ? 'code' : (channel.redeemMode || 'code')
  channelFormProviderType.value = channel.redeemMode === 'external-card' && channel.providerType === 'local'
    ? 'platform-upstream'
    : normalizeChannelProviderValue(channel.providerType)
  channelFormAllowFallback.value = Boolean(channel.allowCommonFallback)
  channelFormAllowDownstreamSale.value = Boolean(channel.allowDownstreamSale)
  channelFormIsActive.value = Boolean(channel.isActive)
  channelFormSortOrder.value = String(channel.sortOrder ?? 0)
  channelDialogOpen.value = true
}

const submitChannelDialog = async () => {
  channelsError.value = ''
  channelsSuccess.value = ''
  try {
    if (channelDialogMode.value === 'create') {
      await adminService.createChannel({
        key: channelFormKey.value.trim(),
        name: channelFormName.value.trim(),
        redeemMode: channelFormRedeemMode.value,
        providerType: channelFormProviderType.value,
        allowCommonFallback: channelFormAllowFallback.value,
        allowDownstreamSale: channelFormAllowDownstreamSale.value,
        isActive: channelFormIsActive.value,
        sortOrder: Number.parseInt(channelFormSortOrder.value || '0', 10) || 0
      })
    } else {
      await adminService.updateChannel(channelFormKey.value, {
        name: channelFormName.value.trim(),
        redeemMode: channelFormRedeemMode.value,
        providerType: channelFormProviderType.value,
        allowCommonFallback: channelFormAllowFallback.value,
        allowDownstreamSale: channelFormAllowDownstreamSale.value,
        isActive: channelFormIsActive.value,
        sortOrder: Number.parseInt(channelFormSortOrder.value || '0', 10) || 0
      })
    }
    channelDialogOpen.value = false
    channelsSuccess.value = 'å·²ä¿å­?
    setTimeout(() => (channelsSuccess.value = ''), 3000)
    await loadChannels()
  } catch (err: any) {
    channelsError.value = err.response?.data?.error || 'ä¿å­å¤±è´¥'
  }
}

const toggleChannelActive = async (channel: Channel) => {
  channelsError.value = ''
  channelsSuccess.value = ''
  try {
    await adminService.updateChannel(channel.key, { isActive: !channel.isActive })
    await loadChannels()
    channelsSuccess.value = 'å·²ä¿å­?
    setTimeout(() => (channelsSuccess.value = ''), 3000)
  } catch (err: any) {
    channelsError.value = err.response?.data?.error || 'æ´æ°å¤±è´¥'
  }
}

const deleteChannel = async (channel: Channel) => {
  if (!confirm(`ç¡®å®è¦å é¤æ¸ éã?{channel.name || channel.key}ãåï¼æ­¤æä½ä¸å¯æ¤éã`)) return
  channelsError.value = ''
  channelsSuccess.value = ''
  try {
    await adminService.deleteChannel(channel.key)
    await loadChannels()
    channelsSuccess.value = 'å·²å é?
    setTimeout(() => (channelsSuccess.value = ''), 3000)
  } catch (err: any) {
    channelsError.value = err.response?.data?.error || 'å é¤å¤±è´¥'
  }
}

const loadPurchaseProducts = async () => {
  if (purchaseProductsLoading.value) return
  purchaseProductsLoading.value = true
  purchaseProductsError.value = ''
  purchaseProductsSuccess.value = ''
  try {
    const response = await adminService.getPurchaseProducts()
    purchaseProducts.value = Array.isArray(response.products) ? response.products : []
  } catch (err: any) {
    purchaseProductsError.value = err.response?.data?.error || 'å è½½ååå¤±è´¥'
  } finally {
    purchaseProductsLoading.value = false
  }
}

const loadPurchaseAvailability = async () => {
  try {
    const meta: PurchaseMeta = await purchaseService.getMeta()
    const map: Record<string, number> = {}
    for (const plan of meta.plans || []) {
      map[plan.key] = Number(plan.availableCount || 0)
    }
    purchaseAvailability.value = map
  } catch {
    purchaseAvailability.value = {}
  }
}

const refreshPurchaseProducts = async () => {
  await Promise.all([loadPurchaseProducts(), loadPurchaseAvailability()])
}

const openCreatePurchaseProductDialog = async () => {
  await ensureSettingsResourceLoaded('channels')
  purchaseProductDialogMode.value = 'create'
  purchaseProductFormKey.value = ''
  purchaseProductFormName.value = ''
  purchaseProductFormAmount.value = ''
  purchaseProductFormServiceDays.value = '30'
  purchaseProductFormOrderType.value = 'warranty'
  purchaseProductFormCodeChannels.value = 'paypal,common'
  purchaseProductFormIsActive.value = true
  purchaseProductFormSortOrder.value = '0'
  purchaseProductDialogOpen.value = true
}

const openEditPurchaseProductDialog = async (product: PurchaseProduct) => {
  await ensureSettingsResourceLoaded('channels')
  purchaseProductDialogMode.value = 'edit'
  purchaseProductFormKey.value = product.productKey
  purchaseProductFormName.value = product.productName
  purchaseProductFormAmount.value = product.amount
  purchaseProductFormServiceDays.value = String(product.serviceDays ?? 30)
  purchaseProductFormOrderType.value = product.orderType
  purchaseProductFormCodeChannels.value = product.codeChannels
  purchaseProductFormIsActive.value = Boolean(product.isActive)
  purchaseProductFormSortOrder.value = String(product.sortOrder ?? 0)
  purchaseProductDialogOpen.value = true
}

const submitPurchaseProductDialog = async () => {
  purchaseProductsError.value = ''
  purchaseProductsSuccess.value = ''

  const payload = {
    productKey: purchaseProductFormKey.value.trim(),
    productName: purchaseProductFormName.value.trim(),
    amount: purchaseProductFormAmount.value.trim(),
    serviceDays: Number.parseInt(purchaseProductFormServiceDays.value || '0', 10),
    orderType: purchaseProductFormOrderType.value,
    codeChannels: purchaseProductFormCodeChannels.value.trim(),
    isActive: purchaseProductFormIsActive.value,
    sortOrder: Number.parseInt(purchaseProductFormSortOrder.value || '0', 10) || 0,
  }

  try {
    if (purchaseProductDialogMode.value === 'create') {
      await adminService.createPurchaseProduct(payload)
    } else {
      await adminService.updatePurchaseProduct(payload.productKey, payload)
    }
    purchaseProductDialogOpen.value = false
    purchaseProductsSuccess.value = 'å·²ä¿å­?
    setTimeout(() => (purchaseProductsSuccess.value = ''), 3000)
    await Promise.all([loadPurchaseProducts(), loadPurchaseAvailability()])
  } catch (err: any) {
    purchaseProductsError.value = err.response?.data?.error || 'ä¿å­å¤±è´¥'
  }
}

const togglePurchaseProductActive = async (product: PurchaseProduct) => {
  purchaseProductsError.value = ''
  purchaseProductsSuccess.value = ''
  try {
    await adminService.updatePurchaseProduct(product.productKey, { isActive: !product.isActive })
    await Promise.all([loadPurchaseProducts(), loadPurchaseAvailability()])
    purchaseProductsSuccess.value = 'å·²ä¿å­?
    setTimeout(() => (purchaseProductsSuccess.value = ''), 3000)
  } catch (err: any) {
    purchaseProductsError.value = err.response?.data?.error || 'æ´æ°å¤±è´¥'
  }
}

const deletePurchaseProduct = async (product: PurchaseProduct) => {
  if (!confirm(`ç¡®å®è¦å é¤ååã?{product.productName || product.productKey}ãåï¼æ­¤æä½ä¸å¯æ¤éã`)) return
  purchaseProductsError.value = ''
  purchaseProductsSuccess.value = ''
  try {
    await adminService.deletePurchaseProduct(product.productKey)
    await Promise.all([loadPurchaseProducts(), loadPurchaseAvailability()])
    purchaseProductsSuccess.value = 'å·²å é?
    setTimeout(() => (purchaseProductsSuccess.value = ''), 3000)
  } catch (err: any) {
    purchaseProductsError.value = err.response?.data?.error || 'å é¤å¤±è´¥'
  }
}

const handleUpdateApiKey = async () => {
  apiKeyError.value = ''
  apiKeySuccess.value = ''

  // Validation
  if (!apiKey.value) {
    apiKeyError.value = 'è¯·è¾å
¥APIå¯é¥'
    return
  }

  if (apiKey.value.length < 16) {
    apiKeyError.value = 'APIå¯é¥è³å°éè¦?16 ä¸ªå­ç¬¦ä»¥ç¡®ä¿å®å
¨æ?
    return
  }

  apiKeyLoading.value = true

  try {
    await userService.updateApiKey(apiKey.value)
    apiKeySuccess.value = 'APIå¯é¥æ´æ°æåï¼è¯·å¨æ²¹ç´èæ¬ä¸­ä½¿ç¨æ°å¯é?

    // Clear success message after 5 seconds
    setTimeout(() => {
      apiKeySuccess.value = ''
    }, 5000)
  } catch (err: any) {
    apiKeyError.value = err.response?.data?.error || 'æ´æ°APIå¯é¥å¤±è´¥ï¼è¯·éè¯'
  } finally {
    apiKeyLoading.value = false
  }
}

// çæéæºAPIå¯é¥
const generateApiKey = () => {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'
  const length = 32
  let result = ''
  for (let i = 0; i < length; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  apiKey.value = result
  showApiKey.value = true // çæåèªå¨æ¾ç¤?
  apiKeySuccess.value = 'â?å·²çæéæºå¯é¥ï¼ç¹å»"æ´æ° API å¯é¥"ä¿å­'
}

// åæ¢æ¾ç¤º/éèAPIå¯é¥
const toggleShowApiKey = () => {
  showApiKey.value = !showApiKey.value
}

const toggleShowSmtpPass = () => {
  showSmtpPass.value = !showSmtpPass.value
}

const toggleShowLinuxdoClientSecret = () => {
  showLinuxdoClientSecret.value = !showLinuxdoClientSecret.value
}

const toggleShowLinuxdoCreditKey = () => {
  showLinuxdoCreditKey.value = !showLinuxdoCreditKey.value
}

const toggleShowZpayKey = () => {
  showZpayKey.value = !showZpayKey.value
}

const toggleShowTurnstileSecretKey = () => {
  showTurnstileSecretKey.value = !showTurnstileSecretKey.value
}

const toggleShowTelegramBotToken = () => {
  showTelegramBotToken.value = !showTelegramBotToken.value
}

const toggleShowUpstreamOutboundApiKey = () => {
  showUpstreamOutboundApiKey.value = !showUpstreamOutboundApiKey.value
}

const toggleShowUpstreamInboundClientApiKey = (index: number) => {
  const target = upstreamInboundClients.value[index]
  if (!target) return
  target.showApiKey = !target.showApiKey
}

const addUpstreamInboundClient = () => {
  upstreamInboundClients.value = [...upstreamInboundClients.value, createUpstreamInboundClientRow()]
}

const removeUpstreamInboundClient = (index: number) => {
  if (upstreamInboundClients.value.length === 1) {
    upstreamInboundClients.value = [createUpstreamInboundClientRow()]
    return
  }
  upstreamInboundClients.value = upstreamInboundClients.value.filter((_, currentIndex) => currentIndex !== index)
}

const loadEmailDomainWhitelist = async () => {
  emailDomainWhitelistError.value = ''
  emailDomainWhitelistSuccess.value = ''
  try {
    const response = await adminService.getEmailDomainWhitelist()
    emailDomainWhitelist.value = (response.domains || []).join(',')
  } catch (err: any) {
    emailDomainWhitelistError.value = err.response?.data?.error || 'å è½½é®ç®±ç½ååå¤±è´?
  }
}

const saveEmailDomainWhitelist = async () => {
  emailDomainWhitelistError.value = ''
  emailDomainWhitelistSuccess.value = ''
  emailDomainWhitelistLoading.value = true
  try {
    const domains = emailDomainWhitelist.value
      .split(',')
      .map(s => s.trim())
      .filter(Boolean)
    await adminService.updateEmailDomainWhitelist(domains)
    emailDomainWhitelistSuccess.value = 'å·²ä¿å­?
    setTimeout(() => (emailDomainWhitelistSuccess.value = ''), 3000)
  } catch (err: any) {
    emailDomainWhitelistError.value = err.response?.data?.error || 'ä¿å­å¤±è´¥'
  } finally {
    emailDomainWhitelistLoading.value = false
  }
}

const loadLinuxDoOAuthSettings = async () => {
  linuxdoOauthError.value = ''
  linuxdoOauthSuccess.value = ''
  try {
    const response = await adminService.getLinuxDoOAuthSettings()
    linuxdoClientId.value = response.oauth?.clientId || ''
    linuxdoRedirectUri.value = response.oauth?.redirectUri || ''
    linuxdoClientSecret.value = ''
    linuxdoClientSecretSet.value = Boolean(response.oauth?.clientSecretSet)
    linuxdoClientSecretStored.value = Boolean(response.oauth?.clientSecretStored)
  } catch (err: any) {
    linuxdoOauthError.value = err.response?.data?.error || 'å è½½ Linux DO OAuth é
ç½®å¤±è´¥'
  }
}

const saveLinuxDoOAuthSettings = async () => {
  linuxdoOauthError.value = ''
  linuxdoOauthSuccess.value = ''

  const clientId = linuxdoClientId.value.trim()
  const redirectUri = linuxdoRedirectUri.value.trim()
  const clientSecretTrimmed = linuxdoClientSecret.value.trim()

  const wantsEnable = Boolean(clientId || redirectUri || clientSecretTrimmed)
  if (wantsEnable) {
    if (!clientId) {
      linuxdoOauthError.value = 'è¯·è¾å
?Linux DO Client ID'
      return
    }
    if (!redirectUri) {
      linuxdoOauthError.value = 'è¯·è¾å
?Linux DO Redirect URI'
      return
    }
    if (!clientSecretTrimmed && !linuxdoClientSecretSet.value) {
      linuxdoOauthError.value = 'è¯·è¾å
?Linux DO Client Secret'
      return
    }

    try {
      const parsed = new URL(redirectUri)
      if (!['http:', 'https:'].includes(parsed.protocol)) {
        linuxdoOauthError.value = 'Redirect URI å¿
é¡»æ?http(s)'
        return
      }
    } catch {
      linuxdoOauthError.value = 'Redirect URI æ ¼å¼ä¸æ­£ç¡?
      return
    }
  }

  linuxdoOauthLoading.value = true
  try {
    const payload: any = {
      oauth: {
        clientId,
        redirectUri,
      },
    }
    if (clientSecretTrimmed) {
      payload.oauth.clientSecret = clientSecretTrimmed
    }

    const response = await adminService.updateLinuxDoOAuthSettings(payload)
    linuxdoClientId.value = response.oauth?.clientId || clientId
    linuxdoRedirectUri.value = response.oauth?.redirectUri || redirectUri
    linuxdoClientSecret.value = ''
    linuxdoClientSecretSet.value = Boolean(response.oauth?.clientSecretSet)
    linuxdoClientSecretStored.value = Boolean(response.oauth?.clientSecretStored)

    linuxdoOauthSuccess.value = 'å·²ä¿å­?
    setTimeout(() => (linuxdoOauthSuccess.value = ''), 3000)
  } catch (err: any) {
    linuxdoOauthError.value = err.response?.data?.error || 'ä¿å­å¤±è´¥'
  } finally {
    linuxdoOauthLoading.value = false
  }
}

const loadLinuxDoCreditSettings = async () => {
  linuxdoCreditError.value = ''
  linuxdoCreditSuccess.value = ''
  try {
    const response = await adminService.getLinuxDoCreditSettings()
    linuxdoCreditPid.value = response.credit?.pid || ''
    linuxdoCreditKey.value = ''
    linuxdoCreditKeySet.value = Boolean(response.credit?.keySet)
    linuxdoCreditKeyStored.value = Boolean(response.credit?.keyStored)
  } catch (err: any) {
    linuxdoCreditError.value = err.response?.data?.error || 'å è½½ Linux DO Credit é
ç½®å¤±è´¥'
  }
}

const saveLinuxDoCreditSettings = async () => {
  linuxdoCreditError.value = ''
  linuxdoCreditSuccess.value = ''

  const pid = linuxdoCreditPid.value.trim()
  const keyTrimmed = linuxdoCreditKey.value.trim()
  const wantsEnable = Boolean(pid || keyTrimmed)

  if (wantsEnable) {
    if (!pid) {
      linuxdoCreditError.value = 'è¯·è¾å
?Credit PID'
      return
    }
    if (!keyTrimmed && !linuxdoCreditKeySet.value) {
      linuxdoCreditError.value = 'è¯·è¾å
?Credit KEY'
      return
    }
  }

  linuxdoCreditLoading.value = true
  try {
    const payload: any = { credit: { pid } }
    if (keyTrimmed) {
      payload.credit.key = keyTrimmed
    }
    const response = await adminService.updateLinuxDoCreditSettings(payload)
    linuxdoCreditPid.value = response.credit?.pid || pid
    linuxdoCreditKey.value = ''
    linuxdoCreditKeySet.value = Boolean(response.credit?.keySet)
    linuxdoCreditKeyStored.value = Boolean(response.credit?.keyStored)

    linuxdoCreditSuccess.value = 'å·²ä¿å­?
    setTimeout(() => (linuxdoCreditSuccess.value = ''), 3000)
  } catch (err: any) {
    linuxdoCreditError.value = err.response?.data?.error || 'ä¿å­å¤±è´¥'
  } finally {
    linuxdoCreditLoading.value = false
  }
}

const loadZpaySettings = async () => {
  zpayError.value = ''
  zpaySuccess.value = ''
  try {
    const response = await adminService.getZpaySettings()
    zpayBaseUrl.value = response.zpay?.baseUrl || 'https://zpayz.cn'
    zpayPid.value = response.zpay?.pid || ''
    zpayKey.value = ''
    zpayKeySet.value = Boolean(response.zpay?.keySet)
    zpayKeyStored.value = Boolean(response.zpay?.keyStored)
  } catch (err: any) {
    zpayError.value = err.response?.data?.error || 'å è½½ ZPAY é
ç½®å¤±è´¥'
  }
}

const saveZpaySettings = async () => {
  zpayError.value = ''
  zpaySuccess.value = ''

  const baseUrl = zpayBaseUrl.value.trim()
  if (baseUrl) {
    try {
      const parsed = new URL(baseUrl)
      if (!['http:', 'https:'].includes(parsed.protocol)) {
        zpayError.value = 'ZPAY Base URL å¿
é¡»æ?http(s)'
        return
      }
    } catch {
      zpayError.value = 'ZPAY Base URL æ ¼å¼ä¸æ­£ç¡?
      return
    }
  }

  const pid = zpayPid.value.trim()
  const keyTrimmed = zpayKey.value.trim()
  if (pid) {
    if (!keyTrimmed && !zpayKeySet.value) {
      zpayError.value = 'è¯·è¾å
?ZPAY KEY'
      return
    }
  }

  zpayLoading.value = true
  try {
    const payload: any = { zpay: { baseUrl, pid } }
    if (keyTrimmed) {
      payload.zpay.key = keyTrimmed
    }
    const response = await adminService.updateZpaySettings(payload)
    zpayBaseUrl.value = response.zpay?.baseUrl || baseUrl || 'https://zpayz.cn'
    zpayPid.value = response.zpay?.pid || pid
    zpayKey.value = ''
    zpayKeySet.value = Boolean(response.zpay?.keySet)
    zpayKeyStored.value = Boolean(response.zpay?.keyStored)

    zpaySuccess.value = 'å·²ä¿å­?
    setTimeout(() => (zpaySuccess.value = ''), 3000)
  } catch (err: any) {
    zpayError.value = err.response?.data?.error || 'ä¿å­å¤±è´¥'
  } finally {
    zpayLoading.value = false
  }
}

const loadDownstreamSaleSettings = async () => {
  downstreamSaleError.value = ''
  downstreamSaleSuccess.value = ''
  try {
    const response = await adminService.getDownstreamSaleSettings()
    downstreamSaleEnabled.value = Boolean(response.downstreamSale?.enabled)
    downstreamSaleProductName.value = response.downstreamSale?.productName || ''
    downstreamSaleAmount.value = response.downstreamSale?.amount || '9.90'
    downstreamSalePayAlipayEnabled.value = response.downstreamSale?.payAlipayEnabled !== false
    downstreamSalePayWxpayEnabled.value = Boolean(response.downstreamSale?.payWxpayEnabled)
  } catch (err: any) {
    downstreamSaleError.value = err.response?.data?.error || 'å è½½ä¸æ¸¸å®ç é
ç½®å¤±è´¥'
  }
}

const saveDownstreamSaleSettings = async () => {
  downstreamSaleError.value = ''
  downstreamSaleSuccess.value = ''

  const productName = downstreamSaleProductName.value.trim()
  const amount = downstreamSaleAmount.value.trim()
  if (!productName) {
    downstreamSaleError.value = 'è¯·è¾å
¥ä¸æ¸¸å®ç ååå'
    return
  }
  if (!amount) {
    downstreamSaleError.value = 'è¯·è¾å
¥ä¸æ¸¸ç»ä¸å®ä»·'
    return
  }
  if (!downstreamSalePayAlipayEnabled.value && !downstreamSalePayWxpayEnabled.value) {
    downstreamSaleError.value = 'æ¯ä»å®åå¾®ä¿¡è³å°å¯ç¨ä¸ä¸?
    return
  }

  downstreamSaleLoading.value = true
  try {
    const response = await adminService.updateDownstreamSaleSettings({
      downstreamSale: {
        enabled: downstreamSaleEnabled.value,
        productName,
        amount,
        payAlipayEnabled: downstreamSalePayAlipayEnabled.value,
        payWxpayEnabled: downstreamSalePayWxpayEnabled.value,
      }
    })
    downstreamSaleEnabled.value = Boolean(response.downstreamSale?.enabled)
    downstreamSaleProductName.value = response.downstreamSale?.productName || productName
    downstreamSaleAmount.value = response.downstreamSale?.amount || amount
    downstreamSalePayAlipayEnabled.value = response.downstreamSale?.payAlipayEnabled !== false
    downstreamSalePayWxpayEnabled.value = Boolean(response.downstreamSale?.payWxpayEnabled)
    downstreamSaleSuccess.value = 'å·²ä¿å­?
    setTimeout(() => (downstreamSaleSuccess.value = ''), 3000)
  } catch (err: any) {
    downstreamSaleError.value = err.response?.data?.error || 'ä¿å­å¤±è´¥'
  } finally {
    downstreamSaleLoading.value = false
  }
}

const loadTurnstileSettings = async () => {
  turnstileError.value = ''
  turnstileSuccess.value = ''
  try {
    const response = await adminService.getTurnstileSettings()
    turnstileSiteKey.value = response.turnstile?.siteKey || ''
    turnstileSecretKey.value = ''
    turnstileEnabled.value = Boolean(response.enabled)
    turnstileSecretSet.value = Boolean(response.turnstile?.secretSet)
    turnstileSecretStored.value = Boolean(response.turnstile?.secretStored)
    turnstileSiteKeyStored.value = Boolean(response.turnstile?.siteKeyStored)
  } catch (err: any) {
    turnstileError.value = err.response?.data?.error || 'å è½½ Turnstile é
ç½®å¤±è´¥'
  }
}

const saveTurnstileSettings = async () => {
  turnstileError.value = ''
  turnstileSuccess.value = ''

  const siteKey = turnstileSiteKey.value.trim()
  const secretTrimmed = turnstileSecretKey.value.trim()

  turnstileLoading.value = true
  try {
    const payload: any = { turnstile: { siteKey } }
    if (secretTrimmed) {
      payload.turnstile.secretKey = secretTrimmed
    }

    const response = await adminService.updateTurnstileSettings(payload)
    turnstileSiteKey.value = response.turnstile?.siteKey || siteKey
    turnstileSecretKey.value = ''
    turnstileEnabled.value = Boolean(response.enabled)
    turnstileSecretSet.value = Boolean(response.turnstile?.secretSet)
    turnstileSecretStored.value = Boolean(response.turnstile?.secretStored)
    turnstileSiteKeyStored.value = Boolean(response.turnstile?.siteKeyStored)

    turnstileSuccess.value = 'å·²ä¿å­?
    setTimeout(() => (turnstileSuccess.value = ''), 3000)
  } catch (err: any) {
    turnstileError.value = err.response?.data?.error || 'ä¿å­å¤±è´¥'
  } finally {
    turnstileLoading.value = false
  }
}

const loadTelegramSettings = async () => {
  telegramError.value = ''
  telegramSuccess.value = ''
  try {
    const response = await adminService.getTelegramSettings()
    telegramAllowedUserIds.value = response.telegram?.allowedUserIds || ''
    telegramAllowedUserIdsStored.value = Boolean(response.telegram?.allowedUserIdsStored)
    telegramBotToken.value = ''
    telegramTokenSet.value = Boolean(response.telegram?.tokenSet)
    telegramTokenStored.value = Boolean(response.telegram?.tokenStored)
    telegramNotifyEnabled.value = response.telegram?.notifyEnabled === false ? 'false' : 'true'
    telegramNotifyEnabledStored.value = Boolean(response.telegram?.notifyEnabledStored)
    telegramNotifyChatIds.value = response.telegram?.notifyChatIds || ''
    telegramNotifyChatIdsStored.value = Boolean(response.telegram?.notifyChatIdsStored)
    telegramNotifyTimeoutMs.value = String(response.telegram?.notifyTimeoutMs ?? 8000)
    telegramNotifyTimeoutMsStored.value = Boolean(response.telegram?.notifyTimeoutMsStored)
  } catch (err: any) {
    telegramError.value = err.response?.data?.error || 'å è½½ Telegram é
ç½®å¤±è´¥'
  }
}

const saveTelegramSettings = async () => {
  telegramError.value = ''
  telegramSuccess.value = ''

  const allowedIdsRaw = telegramAllowedUserIds.value.trim()
  if (allowedIdsRaw) {
    const items = allowedIdsRaw
      .split(',')
      .map(item => item.trim())
      .filter(Boolean)
    const invalid = items.find(item => !/^\d+$/.test(item))
    if (invalid) {
      telegramError.value = `å
è®¸çç¨æ?ID æ ¼å¼ä¸æ­£ç¡®ï¼${invalid}`
      return
    }
  }

  const notifyChatIdsRaw = telegramNotifyChatIds.value.trim()
  if (notifyChatIdsRaw) {
    const items = notifyChatIdsRaw
      .split(',')
      .map(item => item.trim())
      .filter(Boolean)
    const invalid = items.find(item => !/^-?\d+$/.test(item) && !/^@[\w_]{5,32}$/.test(item))
    if (invalid) {
      telegramError.value = `éç¥ chat_id æ ¼å¼ä¸æ­£ç¡®ï¼${invalid}`
      return
    }
  }

  const notifyTimeoutRaw = telegramNotifyTimeoutMs.value.trim()
  const notifyTimeoutMs = Number.parseInt(notifyTimeoutRaw, 10)
  if (!Number.isFinite(notifyTimeoutMs) || notifyTimeoutMs <= 0) {
    telegramError.value = 'éç¥è¶
æ¶æ¶é´éä¸ºæ­£æ´æ°ï¼æ¯«ç§ï¼'
    return
  }

  telegramLoading.value = true
  try {
    const payload: any = { telegram: { allowedUserIds: allowedIdsRaw } }
    const tokenTrimmed = telegramBotToken.value.trim()
    if (tokenTrimmed) {
      payload.telegram.botToken = tokenTrimmed
    }
    payload.telegram.notifyEnabled = telegramNotifyEnabled.value === 'true'
    payload.telegram.notifyChatIds = notifyChatIdsRaw
    payload.telegram.notifyTimeoutMs = notifyTimeoutMs

    const response = await adminService.updateTelegramSettings(payload)
    telegramAllowedUserIds.value = response.telegram?.allowedUserIds || allowedIdsRaw
    telegramAllowedUserIdsStored.value = Boolean(response.telegram?.allowedUserIdsStored)
    telegramBotToken.value = ''
    telegramTokenSet.value = Boolean(response.telegram?.tokenSet)
    telegramTokenStored.value = Boolean(response.telegram?.tokenStored)
    telegramNotifyEnabled.value = response.telegram?.notifyEnabled === false ? 'false' : 'true'
    telegramNotifyEnabledStored.value = Boolean(response.telegram?.notifyEnabledStored)
    telegramNotifyChatIds.value = response.telegram?.notifyChatIds || notifyChatIdsRaw
    telegramNotifyChatIdsStored.value = Boolean(response.telegram?.notifyChatIdsStored)
    telegramNotifyTimeoutMs.value = String(response.telegram?.notifyTimeoutMs ?? notifyTimeoutMs)
    telegramNotifyTimeoutMsStored.value = Boolean(response.telegram?.notifyTimeoutMsStored)

    telegramSuccess.value = 'å·²ä¿å­ï¼Bot Token ä¿®æ¹ééå¯åç«¯çæï¼éç¥é
ç½®å®æ¶çæï¼?
    setTimeout(() => (telegramSuccess.value = ''), 3000)
  } catch (err: any) {
    telegramError.value = err.response?.data?.error || 'ä¿å­å¤±è´¥'
  } finally {
    telegramLoading.value = false
  }
}

const loadProxySettings = async () => {
  proxyError.value = ''
  proxySuccess.value = ''
  try {
    const response = await adminService.getProxySettings()
    setProxyRowsFromText(response.proxy?.proxyUrls || '')
    proxyStored.value = Boolean(response.proxy?.stored)
    proxyEffectiveCount.value = Number(response.proxy?.effectiveCount ?? 0)
    resetProxyTestState()
  } catch (err: any) {
    proxyError.value = err.response?.data?.error || 'å è½½ä»£çé
ç½®å¤±è´¥'
  }
}

const saveProxySettings = async () => {
  proxyError.value = ''
  proxySuccess.value = ''
  proxyLoading.value = true
  try {
    const response = await adminService.updateProxySettings({
      proxy: {
        proxyUrls: proxyDraftProxyUrls.value,
      }
    })
    setProxyRowsFromText(response.proxy?.proxyUrls || '')
    proxyStored.value = Boolean(response.proxy?.stored)
    proxyEffectiveCount.value = Number(response.proxy?.effectiveCount ?? 0)
    resetProxyTestState()
    proxySuccess.value = 'å·²ä¿å­?
    setTimeout(() => (proxySuccess.value = ''), 3000)
  } catch (err: any) {
    proxyError.value = err.response?.data?.error || 'ä¿å­å¤±è´¥'
  } finally {
    proxyLoading.value = false
  }
}

const testProxySettings = async () => {
  proxyError.value = ''
  if (!proxyDraftCount.value) {
    proxyError.value = 'è¯·å
å¡«åè³å°ä¸ä¸ªä»£ç?
    resetProxyTestState()
    return
  }
  proxyTesting.value = true
  resetProxyTestState()
  try {
    const response = await adminService.testProxySettings({
      proxy: {
        proxyUrls: proxyDraftProxyUrls.value,
      }
    })
    proxyTestTotal.value = Number(response.total ?? 0)
    proxyTestPassed.value = Number(response.passed ?? 0)
    proxyTestFailed.value = Number(response.failed ?? 0)
    proxyTestResults.value = Array.isArray(response.results) ? response.results : []
    proxyLastTestedProxyUrls.value = proxyDraftProxyUrls.value
  } catch (err: any) {
    proxyError.value = err.response?.data?.error || 'æµè¯å¤±è´¥'
  } finally {
    proxyTesting.value = false
  }
}

const loadUpstreamSettings = async () => {
  upstreamError.value = ''
  upstreamSuccess.value = ''
  try {
    const response = await adminService.getUpstreamSettings()
    upstreamProviderEnabled.value = response.upstream?.providerEnabled ? 'true' : 'false'
    upstreamProviderType.value = normalizeUpstreamProviderValue(response.upstream?.providerType)
    upstreamSupplierName.value = response.upstream?.supplierName || ''
    upstreamBaseUrl.value = response.upstream?.baseUrl || ''
    upstreamCustomUrl.value = response.upstream?.customUrl || ''
    upstreamCustomBodyTemplate.value = response.upstream?.customBodyTemplate || DEFAULT_UPSTREAM_CUSTOM_BODY_TEMPLATE
    upstreamTimeoutMs.value = String(response.upstream?.timeoutMs ?? 15000)
    upstreamOutboundApiKey.value = ''
    upstreamOutboundApiKeySet.value = Boolean(response.upstream?.outboundApiKeySet)
    upstreamOutboundApiKeyStored.value = Boolean(response.upstream?.outboundApiKeyStored)
    upstreamApiEnabled.value = response.upstream?.apiEnabled ? 'true' : 'false'
    upstreamPublicBaseUrl.value = response.upstream?.publicBaseUrl || ''
    upstreamPublicBaseUrlStored.value = Boolean(response.upstream?.publicBaseUrlStored)
    const inboundClients = Array.isArray(response.upstream?.inboundClients)
      ? response.upstream.inboundClients
      : []
    upstreamInboundClients.value = inboundClients.length > 0
      ? inboundClients.map(client => createUpstreamInboundClientRow({
        id: client.id || '',
        domain: client.domain || '',
        apiKey: '',
        apiKeySet: Boolean(client.apiKeySet),
        apiKeyStored: Boolean(client.apiKeyStored),
        legacy: Boolean(client.legacy),
        showApiKey: false,
      }))
      : [createUpstreamInboundClientRow()]
  } catch (err: any) {
    upstreamError.value = err.response?.data?.error || 'å è½½ä¸ä¸æ¸¸æ¥å£é
ç½®å¤±è´?
  }
}

const saveUpstreamSettings = async () => {
  upstreamError.value = ''
  upstreamSuccess.value = ''
  const providerEnabled = upstreamProviderEnabled.value === 'true'
  const providerType = normalizeUpstreamProviderValue(upstreamProviderType.value)
  const baseUrl = upstreamBaseUrl.value.trim()
  const customUrl = upstreamCustomUrl.value.trim()
  const customBodyTemplate = upstreamCustomBodyTemplate.value.trim() || DEFAULT_UPSTREAM_CUSTOM_BODY_TEMPLATE

  if (providerType === 'platform-upstream') {
    if (providerEnabled && !baseUrl) {
      upstreamError.value = 'å¯ç¨å¹³å°éç¨æ¥å£æ¶å¿
é¡»å¡«åå¹³å?Base URL'
      return
    }

    if (baseUrl) {
      try {
        const parsed = new URL(baseUrl)
        if (!['http:', 'https:'].includes(parsed.protocol)) {
          upstreamError.value = 'ä¸æ¸¸ Base URL å¿
é¡»æ?http(s)'
          return
        }
      } catch {
        upstreamError.value = 'ä¸æ¸¸ Base URL æ ¼å¼ä¸æ­£ç¡?
        return
      }
    }
  }

  if (providerType === 'custom-http') {
    if (providerEnabled && !customUrl) {
      upstreamError.value = 'å¯ç¨èªå®ä¹æ¥å£æ¶å¿
é¡»å¡«åè¯·æ± URL'
      return
    }

    if (customUrl) {
      try {
        const parsed = new URL(customUrl)
        if (!['http:', 'https:'].includes(parsed.protocol)) {
          upstreamError.value = 'èªå®ä¹æ¥å?URL å¿
é¡»æ?http(s)'
          return
        }
      } catch {
        upstreamError.value = 'èªå®ä¹æ¥å?URL æ ¼å¼ä¸æ­£ç¡?
        return
      }
    }

    try {
      JSON.parse(customBodyTemplate)
    } catch {
      upstreamError.value = 'èªå®ä¹æ¥å?Body JSON æ ¼å¼ä¸æ­£ç¡®ï¼æå ä½ç¬¦ä½ç½®ä¸åæ³?
      return
    }
  }

  const timeoutMs = Number.parseInt(upstreamTimeoutMs.value.trim(), 10)
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    upstreamError.value = 'è¶
æ¶æ¶é´éä¸ºæ­£æ´æ°ï¼æ¯«ç§ï¼'
    return
  }

  const publicBaseUrl = upstreamPublicBaseUrl.value.trim()
  if (publicBaseUrl) {
    try {
      const parsed = new URL(publicBaseUrl)
      if (!['http:', 'https:'].includes(parsed.protocol)) {
        upstreamError.value = 'å
¬ç½ Base URL å¿
é¡»æ?http(s)'
        return
      }
    } catch {
      upstreamError.value = 'å
¬ç½ Base URL æ ¼å¼ä¸æ­£ç¡?
      return
    }
  }

  const seenInboundDomains = new Set<string>()
  const inboundClients: Array<{ id?: string; domain: string; apiKey?: string }> = []
  for (let index = 0; index < upstreamInboundClients.value.length; index += 1) {
    const client = upstreamInboundClients.value[index]
    if (!client) continue
    const rawDomain = client.domain.trim()
    const normalizedDomain = normalizeUpstreamInboundDomain(rawDomain)
    const apiKey = client.apiKey.trim()
    const hasPersistedKey = client.apiKeySet
    const isMeaningfulRow = Boolean(rawDomain || apiKey || hasPersistedKey || client.id)

    if (!isMeaningfulRow) continue
    if (rawDomain && !normalizedDomain) {
      upstreamError.value = `ç¬?${index + 1} æ¡ä¸æ¸¸ååæ ¼å¼ä¸æ­£ç¡®`
      return
    }
    if (seenInboundDomains.has(normalizedDomain)) {
      upstreamError.value = normalizedDomain ? `ä¸æ¸¸ååéå¤ï¼?{normalizedDomain}` : 'é»è®¤å
¥ç«è§ååªè½ä¿çä¸æ?
      return
    }
    seenInboundDomains.add(normalizedDomain)
    if (!apiKey && !hasPersistedKey) {
      upstreamError.value = normalizedDomain ? `è¯·ä¸º ${normalizedDomain} å¡«å API Key` : 'è¯·ä¸ºé»è®¤å
¥ç«è§åå¡«å API Key'
      return
    }

    inboundClients.push({
      id: client.id || undefined,
      domain: normalizedDomain,
      apiKey: apiKey || undefined,
    })
  }

  if (upstreamApiEnabled.value === 'true' && inboundClients.length === 0) {
    upstreamError.value = 'å¯ç¨å
¥ç«æ¥å£æ¶ï¼è³å°è¦é
ç½®ä¸ä¸ªä¸æ¸¸ååä¸ API Key'
    return
  }

  upstreamLoading.value = true
  try {
    const payload: any = {
      upstream: {
        providerEnabled,
        providerType,
        supplierName: upstreamSupplierName.value.trim(),
        timeoutMs,
        apiEnabled: upstreamApiEnabled.value === 'true',
        publicBaseUrl,
        inboundClients,
      }
    }

    if (providerType === 'platform-upstream') {
      payload.upstream.baseUrl = baseUrl
    }

    if (providerType === 'custom-http') {
      payload.upstream.customUrl = customUrl
      payload.upstream.customBodyTemplate = customBodyTemplate
    }

    const outboundKey = upstreamOutboundApiKey.value.trim()
    if (providerType === 'platform-upstream' && outboundKey) {
      payload.upstream.outboundApiKey = outboundKey
    }

    const response = await adminService.updateUpstreamSettings(payload)
    upstreamProviderEnabled.value = response.upstream?.providerEnabled ? 'true' : 'false'
    upstreamProviderType.value = normalizeUpstreamProviderValue(response.upstream?.providerType)
    upstreamSupplierName.value = response.upstream?.supplierName || upstreamSupplierName.value.trim()
    upstreamBaseUrl.value = response.upstream?.baseUrl || baseUrl
    upstreamCustomUrl.value = response.upstream?.customUrl || customUrl
    upstreamCustomBodyTemplate.value = response.upstream?.customBodyTemplate || customBodyTemplate
    upstreamTimeoutMs.value = String(response.upstream?.timeoutMs ?? timeoutMs)
    upstreamOutboundApiKey.value = ''
    upstreamOutboundApiKeySet.value = Boolean(response.upstream?.outboundApiKeySet)
    upstreamOutboundApiKeyStored.value = Boolean(response.upstream?.outboundApiKeyStored)
    upstreamApiEnabled.value = response.upstream?.apiEnabled ? 'true' : 'false'
    upstreamPublicBaseUrl.value = response.upstream?.publicBaseUrl || publicBaseUrl
    upstreamPublicBaseUrlStored.value = Boolean(response.upstream?.publicBaseUrlStored)
    const savedInboundClients = Array.isArray(response.upstream?.inboundClients)
      ? response.upstream.inboundClients
      : []
    upstreamInboundClients.value = savedInboundClients.length > 0
      ? savedInboundClients.map(client => createUpstreamInboundClientRow({
        id: client.id || '',
        domain: client.domain || '',
        apiKey: '',
        apiKeySet: Boolean(client.apiKeySet),
        apiKeyStored: Boolean(client.apiKeyStored),
        legacy: Boolean(client.legacy),
        showApiKey: false,
      }))
      : [createUpstreamInboundClientRow()]

    upstreamSuccess.value = 'å·²ä¿å­?
    setTimeout(() => (upstreamSuccess.value = ''), 3000)
  } catch (err: any) {
    upstreamError.value = err.response?.data?.error || 'ä¿å­å¤±è´¥'
  } finally {
    upstreamLoading.value = false
  }
}

const loadSmtpSettings = async () => {
  smtpError.value = ''
  smtpSuccess.value = ''
  try {
    const response = await adminService.getSmtpSettings()
    smtpHost.value = response.smtp?.host || ''
    smtpPort.value = String(response.smtp?.port ?? 465)
    smtpSecure.value = response.smtp?.secure ? 'true' : 'false'
    smtpUser.value = response.smtp?.user || ''
    smtpFrom.value = response.smtp?.from || ''
    adminAlertEmail.value = response.adminAlertEmail || ''
    smtpPass.value = ''
    smtpPassSet.value = Boolean(response.smtp?.passSet)
    smtpPassStored.value = Boolean(response.smtp?.passStored)
  } catch (err: any) {
    smtpError.value = err.response?.data?.error || 'å è½½ SMTP é
ç½®å¤±è´¥'
  }
}

const saveSmtpSettings = async () => {
  smtpError.value = ''
  smtpSuccess.value = ''

  const host = smtpHost.value.trim()
  const port = Number.parseInt(smtpPort.value.trim(), 10)
  if (!Number.isFinite(port) || port <= 0 || port > 65535) {
    smtpError.value = 'è¯·è¾å
¥ææç SMTP ç«¯å£ï¼?-65535ï¼?
    return
  }

  const secure = smtpSecure.value === 'true'
  const user = smtpUser.value.trim()
  const from = smtpFrom.value.trim()
  const recipients = adminAlertEmail.value.trim()

  const passTrimmed = smtpPass.value.trim()

  smtpLoading.value = true
  try {
    const payload: any = {
      smtp: {
        host,
        port,
        secure,
        user,
        from,
      },
      adminAlertEmail: recipients,
    }
    if (passTrimmed) {
      payload.smtp.pass = passTrimmed
    }

    const response = await adminService.updateSmtpSettings(payload)
    smtpHost.value = response.smtp?.host || host
    smtpPort.value = String(response.smtp?.port ?? port)
    smtpSecure.value = response.smtp?.secure ? 'true' : 'false'
    smtpUser.value = response.smtp?.user || user
    smtpFrom.value = response.smtp?.from || from
    adminAlertEmail.value = response.adminAlertEmail || recipients
    smtpPass.value = ''
    smtpPassSet.value = Boolean(response.smtp?.passSet)
    smtpPassStored.value = Boolean(response.smtp?.passStored)
    smtpSuccess.value = 'å·²ä¿å­?
    setTimeout(() => (smtpSuccess.value = ''), 3000)
  } catch (err: any) {
    smtpError.value = err.response?.data?.error || 'ä¿å­å¤±è´¥'
  } finally {
    smtpLoading.value = false
  }
}

const parseYuanToCents = (value: string) => {
  const raw = String(value ?? '').trim()
  if (!raw) return NaN
  if (!/^[0-9]+(\.[0-9]{1,2})?$/.test(raw)) return NaN

  const parts = raw.split('.')
  const yuan = Number.parseInt(parts[0] || '0', 10)
  const centsText = String(parts[1] || '')
  const cents = Number.parseInt((centsText + '00').slice(0, 2), 10)
  return yuan * 100 + cents
}

const loadPointsWithdrawSettings = async () => {
  pointsWithdrawError.value = ''
  pointsWithdrawSuccess.value = ''
  try {
    const response = await adminService.getPointsWithdrawSettings()
    pointsWithdrawRatePoints.value = String(response.rate?.points ?? 1)
    pointsWithdrawRateCashYuan.value = ((Number(response.rate?.cashCents ?? 100) || 0) / 100).toFixed(2)
    pointsWithdrawMinCashYuan.value = ((Number(response.minCashCents ?? 1000) || 0) / 100).toFixed(2)
    pointsWithdrawMinPoints.value = Number(response.minPoints ?? 0)
    pointsWithdrawStepPoints.value = Number(response.stepPoints ?? 0)
  } catch (err: any) {
    pointsWithdrawError.value = err.response?.data?.error || 'å è½½ç§¯åæç°è®¾ç½®å¤±è´¥'
  }
}

const savePointsWithdrawSettings = async () => {
  pointsWithdrawError.value = ''
  pointsWithdrawSuccess.value = ''

  const ratePoints = Number.parseInt(pointsWithdrawRatePoints.value.trim(), 10)
  if (!Number.isFinite(ratePoints) || ratePoints <= 0) {
    pointsWithdrawError.value = 'è¯·è¾å
¥ææçç§¯åæ¯ä¾ï¼æ­£æ´æ°ï¼?
    return
  }

  const rateCashCents = parseYuanToCents(pointsWithdrawRateCashYuan.value)
  if (!Number.isFinite(rateCashCents) || rateCashCents <= 0) {
    pointsWithdrawError.value = 'è¯·è¾å
¥ææçè¿ç°éé¢ï¼å
ï¼?
    return
  }

  const minCashCents = parseYuanToCents(pointsWithdrawMinCashYuan.value)
  if (!Number.isFinite(minCashCents) || minCashCents < 0) {
    pointsWithdrawError.value = 'è¯·è¾å
¥ææçæä½æç°éé¢ï¼å
ï¼'
    return
  }

  pointsWithdrawLoading.value = true
  try {
    const response = await adminService.updatePointsWithdrawSettings({
      ratePoints,
      rateCashCents,
      minCashCents,
    })
    pointsWithdrawRatePoints.value = String(response.rate?.points ?? ratePoints)
    pointsWithdrawRateCashYuan.value = ((Number(response.rate?.cashCents ?? rateCashCents) || 0) / 100).toFixed(2)
    pointsWithdrawMinCashYuan.value = ((Number(response.minCashCents ?? minCashCents) || 0) / 100).toFixed(2)
    pointsWithdrawMinPoints.value = Number(response.minPoints ?? 0)
    pointsWithdrawStepPoints.value = Number(response.stepPoints ?? 0)
    pointsWithdrawSuccess.value = 'å·²ä¿å­?
    setTimeout(() => (pointsWithdrawSuccess.value = ''), 3000)
  } catch (err: any) {
    pointsWithdrawError.value = err.response?.data?.error || 'ä¿å­å¤±è´¥'
  } finally {
    pointsWithdrawLoading.value = false
  }
}

const getSettingsResourceLoader = (resource: SettingsResourceKey) => {
  switch (resource) {
    case 'apiKey':
      return loadApiKey
    case 'featureFlags':
      return loadFeatureFlags
    case 'teamCapacity':
      return loadTeamCapacitySettings
    case 'accountRecovery':
      return loadAccountRecoverySettings
    case 'channels':
      return loadChannels
    case 'purchaseProducts':
      return refreshPurchaseProducts
    case 'downstreamSale':
      return loadDownstreamSaleSettings
    case 'emailWhitelist':
      return loadEmailDomainWhitelist
    case 'pointsWithdraw':
      return loadPointsWithdrawSettings
    case 'smtp':
      return loadSmtpSettings
    case 'linuxdoOauth':
      return loadLinuxDoOAuthSettings
    case 'linuxdoCredit':
      return loadLinuxDoCreditSettings
    case 'zpay':
      return loadZpaySettings
    case 'turnstile':
      return loadTurnstileSettings
    case 'telegram':
      return loadTelegramSettings
    case 'proxy':
      return loadProxySettings
    case 'upstream':
      return loadUpstreamSettings
  }
}

const settingsModuleResources: Record<SettingsModuleId, SettingsResourceKey[]> = {
  general: ['emailWhitelist', 'featureFlags', 'teamCapacity', 'accountRecovery'],
  billing: ['purchaseProducts', 'channels', 'downstreamSale', 'zpay', 'pointsWithdraw'],
  integrations: ['linuxdoOauth', 'linuxdoCredit', 'turnstile', 'telegram'],
  upstream: ['upstream'],
  notifications: ['smtp'],
  security: ['apiKey', 'channels', 'proxy'],
}

const ensureSettingsResourceLoaded = async (
  resource: SettingsResourceKey,
  { force = false }: { force?: boolean } = {}
) => {
  if (!isSuperAdmin.value) return
  if (!force && settingsResourceLoaded.value[resource]) return

                <p class="text-sm" :class="hasNewVersion ? 'text-green-600' : 'text-gray-500'">最新版本</p>
    const pending = settingsResourcePromises.get(resource)
    if (pending) {
      await pending
      return
    }
  }

  const task = (async () => {
    await getSettingsResourceLoader(resource)()
    settingsResourceLoaded.value[resource] = true
  })().finally(() => {
    settingsResourcePromises.delete(resource)
  })

  settingsResourcePromises.set(resource, task)
  await task
}

const ensureSettingsModuleLoaded = async (
  moduleId: SettingsModuleId,
  { force = false }: { force?: boolean } = {}
) => {
  if (!isSuperAdmin.value) return
  await Promise.all(
    settingsModuleResources[moduleId].map(resource => ensureSettingsResourceLoaded(resource, { force }))
  )
}

watch(settingsSubTab, (next) => {
  if (!isSuperAdmin.value || activeTab.value !== 'settings') return
  void ensureSettingsModuleLoaded(next)
}, { immediate: true })

watch(activeTab, (next) => {
  if (!isSuperAdmin.value || next !== 'settings') return
  void ensureSettingsModuleLoaded(settingsSubTab.value)
})
</script>

<template>
  <div class="space-y-6">
    <section class="rounded-[32px] border border-gray-100 bg-white p-6 shadow-sm sm:p-8">
      <div class="mb-6 border-b border-gray-100 pb-5">
        <h1 class="text-2xl font-bold text-gray-900">系统设置</h1>
        <p class="mt-2 text-sm text-gray-500">
          当前页面已切换为稳定版设置面板，优先保证部署、登录和核心兑换流程可正常使用。
        </p>
      </div>

      <div
        v-if="!isSuperAdmin"
        class="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-700"
      >
        系统设置仅对超级管理员开放；如需修改，请使用超级管理员账号登录。
      </div>

      <div v-if="isSuperAdmin" class="grid gap-6 lg:grid-cols-2">
        <section class="rounded-[28px] border border-gray-100 bg-white p-5 shadow-sm">
          <h2 class="text-lg font-semibold text-gray-900">邮箱白名单</h2>
          <p class="mt-1 text-sm text-gray-500">控制注册时允许使用的邮箱域名，多个域名用英文逗号分隔。</p>
          <div class="mt-4 space-y-2">
            <label for="emailDomainWhitelist" class="text-sm font-medium text-gray-700">允许的域名</label>
            <input
              id="emailDomainWhitelist"
              v-model="emailDomainWhitelist"
              type="text"
              placeholder="example.com, company.com"
              class="h-11 w-full rounded-xl border border-gray-200 bg-gray-50 px-3 text-sm outline-none focus:border-blue-500"
            />
            <p class="text-xs text-gray-400">留空表示不限制；支持子域名。</p>
          </div>
          <div v-if="emailDomainWhitelistError" class="mt-4 rounded-xl border border-red-100 bg-red-50 p-4 text-sm font-medium text-red-600">
            {{ emailDomainWhitelistError }}
          </div>
          <div v-if="emailDomainWhitelistSuccess" class="mt-4 rounded-xl border border-green-100 bg-green-50 p-4 text-sm font-medium text-green-600">
            {{ emailDomainWhitelistSuccess }}
          </div>
          <div class="mt-4 flex flex-col gap-3 sm:flex-row">
            <button
              type="button"
              class="h-11 rounded-xl border border-gray-200 px-4 text-sm font-medium text-gray-700 hover:bg-gray-50"
              @click="loadEmailDomainWhitelist"
            >
              刷新
            </button>
            <button
              type="button"
              :disabled="emailDomainWhitelistLoading"
              class="h-11 rounded-xl bg-black px-4 text-sm font-medium text-white hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-60"
              @click="saveEmailDomainWhitelist"
            >
              {{ emailDomainWhitelistLoading ? '保存中...' : '保存邮箱白名单' }}
            </button>
          </div>
        </section>

        <section class="rounded-[28px] border border-gray-100 bg-white p-5 shadow-sm">
          <h2 class="text-lg font-semibold text-gray-900">功能开关</h2>
          <p class="mt-1 text-sm text-gray-500">关闭后，相关页面入口和接口会按配置禁用。</p>
          <div class="mt-4 space-y-3">
            <label class="flex items-center justify-between rounded-2xl border border-gray-100 bg-gray-50 px-4 py-3">
              <span class="text-sm font-medium text-gray-900">小红书功能</span>
              <input v-model="featureFlags.xhs" type="checkbox" class="h-5 w-5 rounded border-gray-300 text-blue-600" />
            </label>
            <label class="flex items-center justify-between rounded-2xl border border-gray-100 bg-gray-50 px-4 py-3">
              <span class="text-sm font-medium text-gray-900">闲鱼功能</span>
              <input v-model="featureFlags.xianyu" type="checkbox" class="h-5 w-5 rounded border-gray-300 text-blue-600" />
            </label>
            <label class="flex items-center justify-between rounded-2xl border border-gray-100 bg-gray-50 px-4 py-3">
              <span class="text-sm font-medium text-gray-900">支付功能</span>
              <input v-model="featureFlags.payment" type="checkbox" class="h-5 w-5 rounded border-gray-300 text-blue-600" />
            </label>
            <label class="flex items-center justify-between rounded-2xl border border-gray-100 bg-gray-50 px-4 py-3">
              <span class="text-sm font-medium text-gray-900">开放账号 / Credit 功能</span>
              <input v-model="featureFlags.openAccounts" type="checkbox" class="h-5 w-5 rounded border-gray-300 text-blue-600" />
            </label>
          </div>
          <div v-if="featureFlagsError" class="mt-4 rounded-xl border border-red-100 bg-red-50 p-4 text-sm font-medium text-red-600">
            {{ featureFlagsError }}
          </div>
          <div v-if="featureFlagsSuccess" class="mt-4 rounded-xl border border-green-100 bg-green-50 p-4 text-sm font-medium text-green-600">
            {{ featureFlagsSuccess }}
          </div>
          <div class="mt-4 flex flex-col gap-3 sm:flex-row">
            <button
              type="button"
              class="h-11 rounded-xl border border-gray-200 px-4 text-sm font-medium text-gray-700 hover:bg-gray-50"
              @click="loadFeatureFlags"
            >
              刷新
            </button>
            <button
              type="button"
              :disabled="featureFlagsLoading"
              class="h-11 rounded-xl bg-black px-4 text-sm font-medium text-white hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-60"
              @click="saveFeatureFlags"
            >
              {{ featureFlagsLoading ? '保存中...' : '保存功能开关' }}
            </button>
          </div>
        </section>

        <section class="rounded-[28px] border border-gray-100 bg-white p-5 shadow-sm lg:col-span-2">
          <h2 class="text-lg font-semibold text-gray-900">Team 容量设置</h2>
          <p class="mt-1 text-sm text-gray-500">设置单个母号允许容纳的总席位上限。兑换时会按这个容量自动分配。</p>
          <div class="mt-4 max-w-xs space-y-2">
            <label for="teamCapacityLimit" class="text-sm font-medium text-gray-700">单母号总席位</label>
            <input
              id="teamCapacityLimit"
              v-model="teamCapacityLimit"
              type="number"
              min="1"
              max="999"
              placeholder="5"
              class="h-11 w-full rounded-xl border border-gray-200 bg-gray-50 px-3 text-sm outline-none focus:border-blue-500"
            />
            <p class="text-xs text-gray-400">支持 1 到 999 的任意正整数。</p>
          </div>
          <div v-if="teamCapacityError" class="mt-4 rounded-xl border border-red-100 bg-red-50 p-4 text-sm font-medium text-red-600">
            {{ teamCapacityError }}
          </div>
          <div v-if="teamCapacitySuccess" class="mt-4 rounded-xl border border-green-100 bg-green-50 p-4 text-sm font-medium text-green-600">
            {{ teamCapacitySuccess }}
          </div>
          <div class="mt-4 flex flex-col gap-3 sm:flex-row">
            <button
              type="button"
              class="h-11 rounded-xl border border-gray-200 px-4 text-sm font-medium text-gray-700 hover:bg-gray-50"
              @click="loadTeamCapacitySettings"
            >
              刷新
            </button>
            <button
              type="button"
              :disabled="teamCapacityLoading"
              class="h-11 rounded-xl bg-black px-4 text-sm font-medium text-white hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-60"
              @click="saveTeamCapacitySettings"
            >
              {{ teamCapacityLoading ? '保存中...' : '保存 Team 容量设置' }}
            </button>
          </div>
        </section>
      </div>
    </section>
  </div>
</template>


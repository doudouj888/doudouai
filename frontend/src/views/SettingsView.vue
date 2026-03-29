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
  { id: 'general', label: 'åºç¡è®¾ç½®', desc: 'åè½å¼å
³ãç½ååä¸è¡¥å½?, icon: Settings },
  { id: 'billing', label: 'æ¯ä»ä¸è´¢å?, desc: 'ååãæ¯ä»ééä¸æç?, icon: CreditCard },
  { id: 'integrations', label: 'ç¬¬ä¸æ¹éæ?, desc: 'OAuthãéªè¯ä¸æºå¨äº?, icon: Link },
  { id: 'upstream', label: 'ä¸ä¸æ¸¸æ¥å£é
ç½?, desc: 'åºç«å±¥çº¦ä¸å
¥ç«é´æ?, icon: RefreshCw },
  { id: 'notifications', label: 'é®ä»¶ä¸éç¥', desc: 'SMTP åè­¦é®ä»¶é
ç½®', icon: Mail },
  { id: 'security', label: 'æ ¸å¿ä¸å®å
?, desc: 'API å¯é¥ãæ¸ éä¸ç½ç»', icon: Shield },
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
    .split(/[\n,;]+/g)
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
    .join('\n')
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
  <Tabs v-model="activeTab" class="space-y-8">
    <!-- Header Actions -->
    <Teleport v-if="teleportReady && isSuperAdmin" to="#header-actions">
      <div class="flex items-center gap-3">
        <TabsList class="bg-gray-100/70 border border-gray-200 rounded-xl p-1">
          <TabsTrigger value="settings" class="rounded-lg px-4">
            ç³»ç»è®¾ç½®
          </TabsTrigger>
          <TabsTrigger value="announcements" class="rounded-lg px-4">
            å
¬åç®¡ç
          </TabsTrigger>
        </TabsList>

        <Button
          variant="outline"
          :disabled="versionLoading"
          class="h-10 px-4 border-gray-200 bg-white hover:bg-blue-50 hover:text-blue-600 hover:border-blue-200 rounded-xl transition-all"
          @click="checkForUpdates"
        >
          <RefreshCw v-if="versionLoading" class="w-4 h-4 mr-2 animate-spin" />
          <RefreshCw v-else class="w-4 h-4 mr-2" />
          æ£æ¥æ´æ?
        </Button>
      </div>
    </Teleport>

    <!-- çæ¬æ£æ¥å¯¹è¯æ¡ -->
    <Dialog v-model:open="versionDialogOpen">
      <DialogContent class="sm:max-w-md">
        <DialogHeader>
          <DialogTitle class="text-xl font-bold text-gray-900">çæ¬ä¿¡æ¯</DialogTitle>
          <DialogDescription class="text-gray-500">
            æ¥çå½åçæ¬åææ°çæ¬ä¿¡æ?
          </DialogDescription>
        </DialogHeader>

        <div class="space-y-4 py-4">
          <div v-if="versionError" class="rounded-xl bg-red-50 p-4 text-red-600 border border-red-100 text-sm font-medium">
            {{ versionError }}
          </div>

          <template v-else>
            <div class="flex items-center justify-between p-4 bg-gray-50 rounded-2xl border border-gray-100">
              <div class="space-y-1">
                <p class="text-sm text-gray-500">å½åçæ¬</p>
                <p class="font-mono font-semibold text-gray-900">{{ currentVersion?.version || '-' }}</p>
              </div>
            </div>

            <div class="flex items-center justify-between p-4 rounded-2xl border" :class="hasNewVersion ? 'bg-green-50 border-green-200' : 'bg-gray-50 border-gray-100'">
              <div class="space-y-1">
                <p class="text-sm" :class="hasNewVersion ? 'text-green-600' : 'text-gray-500'">最新版本</p>
                <p class="font-mono font-semibold" :class="hasNewVersion ? 'text-green-700' : 'text-gray-900'">
                </p>
                <p v-if="latestVersion?.publishedAt" class="text-xs text-gray-400">
                  åå¸äº?{{ new Date(latestVersion.publishedAt).toLocaleDateString('zh-CN') }}
                </p>
              </div>
              <div v-if="hasNewVersion" class="flex items-center gap-2">
                <span class="px-2 py-1 text-xs font-medium text-green-700 bg-green-100 rounded-full">ææ°çæ¬</span>
              </div>
            </div>

            <div v-if="hasNewVersion && latestVersion?.htmlUrl" class="pt-2">
              <a
                :href="latestVersion.htmlUrl"
                target="_blank"
                rel="noopener noreferrer"
                class="inline-flex items-center justify-center w-full h-11 px-4 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-xl transition-colors"
              >
                åå¾ GitHub æ¥çæ°çæ?
              </a>
            </div>

            <div v-else-if="!hasNewVersion && currentVersion" class="text-center text-sm text-gray-500 py-2">
              å·²æ¯ææ°çæ?
            </div>
          </template>
        </div>
      </DialogContent>
    </Dialog>

    <TabsContent value="settings" class="mt-0">
      <!-- éè¶
çº§ç®¡çåæç¤º -->
      <Card
        v-if="!isSuperAdmin"
        class="bg-white rounded-[32px] border border-gray-100 shadow-sm overflow-hidden flex flex-col lg:col-span-2"
      >
        <CardHeader class="border-b border-gray-50 bg-gray-50/30 px-6 py-5 sm:px-8 sm:py-6">
          <CardTitle class="text-xl font-bold text-gray-900">系统设置</CardTitle>
          <CardDescription class="text-gray-500">
            系统设置仅对超级管理员开放；普通管理员如需调整，请联系超级管理员。
          </CardDescription>
        </CardHeader>
      </Card>

      <div v-else class="space-y-6">
        <!-- é¡¶é¨åç±»å¯¼èª (sticky) -->
        <div class="sticky -top-4 lg:-top-8 z-20 -mx-4 px-4 lg:-mx-8 lg:px-8 pt-4 lg:pt-8 pb-3 bg-[#F5F5F7]/90 backdrop-blur-md border-b border-gray-200/60">
          <nav class="flex items-center gap-1.5 overflow-x-auto scrollbar-hide -mb-px">
            <button
              v-for="nav in settingsNav"
              :key="nav.id"
              @click="settingsSubTab = nav.id"
              class="group relative flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all shrink-0"
              :class="settingsSubTab === nav.id
                ? 'text-blue-700 bg-blue-50'
                : 'text-gray-500 hover:text-gray-800 hover:bg-gray-50'"
            >
              <component
                :is="nav.icon"
                class="w-4 h-4 shrink-0"
                :class="settingsSubTab === nav.id ? 'text-blue-600' : 'text-gray-400 group-hover:text-gray-600'"
              />
              <span>{{ nav.label }}</span>
            </button>
          </nav>
        </div>

        <!-- å
å®¹å?-->
        <div class="space-y-6">
          <!-- å½ååç±»æ é¢ -->
          <div class="flex items-center gap-3">
            <div class="flex items-center justify-center w-9 h-9 rounded-xl bg-blue-50 text-blue-600">
              <component :is="activeNavItem?.icon" class="w-[18px] h-[18px]" />
            </div>
            <div>
              <h2 class="text-base font-bold text-gray-900">{{ activeNavItem?.label }}</h2>
              <p class="text-xs text-gray-500">{{ activeNavItem?.desc }}</p>
            </div>
          </div>

          <!-- å¡çåè¡¨ -->
          <div class="grid gap-6 lg:grid-cols-2">
            <template v-if="settingsSubTab === 'security'">
            <!-- APIå¯é¥ç®¡ç -->
      <Card
        v-if="isSuperAdmin"
        class="bg-white rounded-[32px] border border-gray-100 shadow-sm overflow-hidden flex flex-col lg:col-span-2"
      >
        <CardHeader class="border-b border-gray-50 bg-gray-50/30 px-6 py-5 sm:px-8 sm:py-6">
          <div class="flex items-center gap-3 mb-1">
            <div class="w-10 h-10 rounded-2xl bg-purple-50 flex items-center justify-center text-purple-600">
              <KeyRound class="w-5 h-5" />
            </div>
            <CardTitle class="text-xl font-bold text-gray-900">API å¯é¥</CardTitle>
          </div>
          <CardDescription class="text-gray-500 pl-[52px]">ç¨äºå¤é¨è°ç¨APIæ¥å£ã</CardDescription>
        </CardHeader>
        <CardContent class="p-6 sm:p-8 space-y-6 flex-1">
          <form @submit.prevent="handleUpdateApiKey" class="space-y-5">
            <div class="space-y-2">
              <Label for="apiKey" class="text-xs font-semibold text-gray-500 uppercase tracking-wider">API å¯é¥</Label>
              <div class="flex flex-col sm:flex-row gap-3">
                <div class="relative w-full sm:flex-1">
                  <Input
                  <Input
                    id="apiKey"
                    v-model="apiKey"
                    :type="showApiKey ? 'text' : 'password'"
                    placeholder="请输入至少 16 位的 API 密钥"
                    required
                    class="h-11 pr-10 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-purple-100 focus:border-purple-500 transition-all font-mono text-sm"
                  />
                    class="h-11 pr-10 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-purple-100 focus:border-purple-500 transition-all font-mono text-sm"
                  />
                  <button
                    type="button"
                    @click="toggleShowApiKey"
                    class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                  >
                    <EyeOff v-if="showApiKey" class="h-4 w-4" />
                    <Eye v-else class="h-4 w-4" />
                  </button>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  @click="generateApiKey"
                  class="w-full sm:w-auto h-11 px-4 border-gray-200 hover:bg-purple-50 hover:text-purple-600 hover:border-purple-200 rounded-xl transition-all"
                >
                  <Sparkles class="h-4 w-4 mr-2" />
                  çæ
                </Button>
              </div>
              <p class="text-xs text-gray-400">å»ºè®®ä½¿ç¨ 32 ä½éæºå­ç¬¦ã</p>
            </div>

            <div v-if="apiKeyError" class="rounded-xl bg-red-50 p-4 flex items-center gap-3 text-red-600 border border-red-100">
              <AlertCircle class="w-5 h-5 flex-shrink-0" />
              <span class="text-sm font-medium">{{ apiKeyError }}</span>
            </div>

            <div v-if="apiKeySuccess" class="rounded-xl bg-green-50 p-4 flex items-center gap-3 text-green-600 border border-green-100">
              <CheckCircle2 class="w-5 h-5 flex-shrink-0" />
              <span class="text-sm font-medium">{{ apiKeySuccess }}</span>
            </div>

            <Button
              type="submit"
              :disabled="apiKeyLoading"
              class="w-full h-11 rounded-xl bg-purple-600 hover:bg-purple-700 text-white shadow-lg shadow-purple-200"
            >
              {{ apiKeyLoading ? 'æ´æ°ä¸?..' : 'æ´æ° API å¯é¥' }}
            </Button>
          </form>

          <div class="rounded-2xl bg-blue-50/50 border border-blue-100 p-5 space-y-2">
            <p class="text-sm font-semibold text-blue-900 flex items-center gap-2">
              <AlertCircle class="w-4 h-4" />
              å®å
¨æç¤º
            </p>
            <ul class="list-disc list-inside space-y-1 text-xs text-blue-700/80 pl-1">
              <li>å®æè½®æ¢å¯é¥å¯æåå®å
¨æ§ã</li>
              <li>è¯·å¿å°å¯é¥æ³é²ç»ä»äººã</li>
            </ul>
          </div>
        </CardContent>
      </Card>

            </template>

            <template v-if="settingsSubTab === 'general'">
            <!-- é®ç®±åç¼ç½åå?-->
      <Card v-if="isSuperAdmin" class="bg-white rounded-[32px] border border-gray-100 shadow-sm overflow-hidden flex flex-col lg:col-span-2">
        <CardHeader class="border-b border-gray-50 bg-gray-50/30 px-6 py-5 sm:px-8 sm:py-6">
          <CardTitle class="text-xl font-bold text-gray-900">é®ç®±åç¼ç½åå</CardTitle>
          <CardDescription class="text-gray-500">ç¨äºæ³¨åæ¶æ ¡éªé®ç®±ååï¼éå·åéï¼ãçç©ºè¡¨ç¤ºä¸éå¶ã</CardDescription>
        </CardHeader>
        <CardContent class="p-6 sm:p-8 space-y-5 flex-1">
          <div class="space-y-2">
            <Label for="emailDomainWhitelist" class="text-xs font-semibold text-gray-500 uppercase tracking-wider">å
è®¸çåå</Label>
            <Input
              id="emailDomainWhitelist"
              v-model="emailDomainWhitelist"
              type="text"
              placeholder="example.com,company.com"
              class="h-11 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all font-mono text-sm"
            />
            <p class="text-xs text-gray-400">ç¤ºä¾ï¼example.com æ?.example.comï¼å
è®¸å­ååï¼</p>
          </div>

          <div v-if="emailDomainWhitelistError" class="rounded-xl bg-red-50 p-4 text-red-600 border border-red-100 text-sm font-medium">
            {{ emailDomainWhitelistError }}
          </div>

          <div v-if="emailDomainWhitelistSuccess" class="rounded-xl bg-green-50 p-4 text-green-600 border border-green-100 text-sm font-medium">
            {{ emailDomainWhitelistSuccess }}
          </div>

          <Button
            type="button"
            :disabled="emailDomainWhitelistLoading"
            class="w-full h-11 rounded-xl bg-black hover:bg-gray-800 text-white shadow-lg shadow-black/5"
            @click="saveEmailDomainWhitelist"
          >
            {{ emailDomainWhitelistLoading ? '保存中...' : '保存邮箱白名单' }}
          </Button>
        </CardContent>
      </Card>

            <p class="text-xs text-gray-400">支持 1 到 999 的任意正整数；保存后新兑换会按这个上限自动匹配母号。</p>
?-->
      <Card v-if="isSuperAdmin" class="bg-white rounded-[32px] border border-gray-100 shadow-sm overflow-hidden flex flex-col lg:col-span-2">
        <CardHeader class="border-b border-gray-50 bg-gray-50/30 px-6 py-5 sm:px-8 sm:py-6">
          <CardTitle class="text-xl font-bold text-gray-900">åè½å¼å
</CardTitle>
          <CardDescription class="text-gray-500">
            ç¨äºå¿«éå¯ç?ç¦ç¨å¯éæ¨¡åï¼ç¦ç¨åç¸å
³é¡µé?API ä¼è¿å?403 æç¤ºã?
          </CardDescription>
        </CardHeader>
        <CardContent class="p-6 sm:p-8 space-y-5 flex-1">
          <div class="space-y-3">
            <div class="flex items-center justify-between p-4 bg-gray-50 rounded-2xl border border-gray-100">
              <div class="space-y-1">
                <p class="font-medium text-gray-900">å°çº¢ä¹¦ï¼è®¢ååæ­¥/å
æ¢ï¼</p>
              </div>
              刷新
                type="checkbox"
                v-model="featureFlags.xhs"
                class="w-6 h-6 rounded-md border-gray-300 text-blue-600 focus:ring-blue-500"
              />
            </div>

            <div class="flex items-center justify-between p-4 bg-gray-50 rounded-2xl border border-gray-100">
              {{ teamCapacityLoading ? '保存中...' : '保存 Team 容量设置' }}
                <p class="font-medium text-gray-900">é²é±¼ï¼è®¢ååæ­?å
æ¢ï¼</p>
              </div>
              <input
                type="checkbox"
                v-model="featureFlags.xianyu"
                class="w-6 h-6 rounded-md border-gray-300 text-blue-600 focus:ring-blue-500"
              />
            </div>

            <div class="flex items-center justify-between p-4 bg-gray-50 rounded-2xl border border-gray-100">
              <div class="space-y-1">
                <p class="font-medium text-gray-900">æ¯ä»ï¼ZPAYï¼</p>
              </div>
              <input
                type="checkbox"
                v-model="featureFlags.payment"
                class="w-6 h-6 rounded-md border-gray-300 text-blue-600 focus:ring-blue-500"
              />
            </div>

            <div class="flex items-center justify-between p-4 bg-gray-50 rounded-2xl border border-gray-100">
              <div class="space-y-1">
                <p class="font-medium text-gray-900">å¼æ¾è´¦å·ï¼å?Credit è®¢åï¼</p>
              </div>
              <input
                type="checkbox"
                v-model="featureFlags.openAccounts"
                class="w-6 h-6 rounded-md border-gray-300 text-blue-600 focus:ring-blue-500"
              />
            </div>
          </div>

          <div v-if="featureFlagsError" class="rounded-xl bg-red-50 p-4 text-red-600 border border-red-100 text-sm font-medium">
            {{ featureFlagsError }}
          </div>

          <div v-if="featureFlagsSuccess" class="rounded-xl bg-green-50 p-4 text-green-600 border border-green-100 text-sm font-medium">
            {{ featureFlagsSuccess }}
          </div>

          <div class="flex flex-col sm:flex-row gap-3">
            <Button
              type="button"
              variant="outline"
              class="w-full sm:w-auto h-11 px-4 border-gray-200 rounded-xl"
              @click="loadFeatureFlags"
            >
              å·æ°
            </Button>
            <Button
              type="button"
              :disabled="featureFlagsLoading"
              class="w-full h-11 rounded-xl bg-black hover:bg-gray-800 text-white shadow-lg shadow-black/5"
              @click="saveFeatureFlags"
            >
              {{ featureFlagsLoading ? 'ä¿å­ä¸?..' : 'ä¿å­åè½å¼å
? }}
            </Button>
          </div>
        </CardContent>
      </Card>

      <!-- Team 容量设置 -->
      <Card v-if="isSuperAdmin" class="bg-white rounded-[32px] border border-gray-100 shadow-sm overflow-hidden flex flex-col lg:col-span-2">
        <CardHeader class="border-b border-gray-50 bg-gray-50/30 px-6 py-5 sm:px-8 sm:py-6">
          <CardTitle class="text-xl font-bold text-gray-900">Team 容量设置</CardTitle>
          <CardDescription class="text-gray-500">
            设置单个母号允许容纳的总席位上限。兑换、补录、开放账号、库存统计都会使用这里的值。
          </CardDescription>
        </CardHeader>
        <CardContent class="p-6 sm:p-8 space-y-5 flex-1">
          <div class="space-y-2 p-4 bg-gray-50 rounded-2xl border border-gray-100">
            <Label for="teamCapacityLimit" class="text-xs font-semibold text-gray-500 uppercase tracking-wider">单母号总席位</Label>
            <Input
              id="teamCapacityLimit"
              v-model="teamCapacityLimit"
              type="number"
              min="1"
              max="999"
              placeholder="5"
              class="h-11 bg-white border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all font-mono text-sm"
            />
            <p class="text-xs text-gray-400">支持 1 到 999 的任意正整数；保存后新兑换会按这个上限自动匹配母号。</p>
          </div>

          <div v-if="teamCapacityError" class="rounded-xl bg-red-50 p-4 text-red-600 border border-red-100 text-sm font-medium">
            {{ teamCapacityError }}
          </div>

          <div v-if="teamCapacitySuccess" class="rounded-xl bg-green-50 p-4 text-green-600 border border-green-100 text-sm font-medium">
            {{ teamCapacitySuccess }}
          </div>

          <div class="flex flex-col sm:flex-row gap-3">
            <Button
              type="button"
              variant="outline"
              class="w-full sm:w-auto h-11 px-4 border-gray-200 rounded-xl"
              @click="loadTeamCapacitySettings"
            >
              刷新
            </Button>
            <Button
              type="button"
              :disabled="teamCapacityLoading"
              class="w-full h-11 rounded-xl bg-black hover:bg-gray-800 text-white shadow-lg shadow-black/5"
              @click="saveTeamCapacitySettings"
            >
              {{ teamCapacityLoading ? '保存中...' : '保存 Team 容量设置' }}
            </Button>
          </div>
        </CardContent>
      </Card>

      <!-- è¡¥å½è®¾ç½® -->
      <Card v-if="isSuperAdmin" class="bg-white rounded-[32px] border border-gray-100 shadow-sm overflow-hidden flex flex-col lg:col-span-2">
        <CardHeader class="border-b border-gray-50 bg-gray-50/30 px-6 py-5 sm:px-8 sm:py-6">
          <CardTitle class="text-xl font-bold text-gray-900">è¡¥å½è®¾ç½®</CardTitle>
          <CardDescription class="text-gray-500">
            æ§å¶è¡¥å½æ¶å¯ç¨å
æ¢ç çåå»ºæ¶é´çªå£ï¼ä»¥åæ¯å¦å¼ºå¶è´¦å·è¿æè¦çè®¢åæªæ­¢æ¥ã?
          </CardDescription>
        </CardHeader>
        <CardContent class="p-6 sm:p-8 space-y-5 flex-1">
          <div class="space-y-3">
            <div class="flex items-center justify-between p-4 bg-gray-50 rounded-2xl border border-gray-100">
              <div class="space-y-1">
                <p class="font-medium text-gray-900">å¼ºå¶ä»
ä½¿ç¨å½å¤©æ°åå»ºçå
æ¢ç </p>
                <p class="text-xs text-gray-500">å
³é­åé»è®¤ä½¿ç¨è¿ 7 å¤©å
åå»ºçå
æ¢ç ï¼å¯èªå®ä¹ï¼ã</p>
              </div>
              <input
                type="checkbox"
                v-model="accountRecoveryForceTodayCodes"
                class="w-6 h-6 rounded-md border-gray-300 text-blue-600 focus:ring-blue-500"
              />
            </div>

            <div v-if="!accountRecoveryForceTodayCodes" class="space-y-2 p-4 bg-gray-50 rounded-2xl border border-gray-100">
              <Label for="accountRecoveryCodeWindowDays" class="text-xs font-semibold text-gray-500 uppercase tracking-wider">å
æ¢ç åå»ºèå´ï¼å¤©ï¼</Label>
              <Input
                id="accountRecoveryCodeWindowDays"
                v-model="accountRecoveryCodeWindowDays"
                type="number"
                min="1"
                max="365"
                placeholder="7"
                class="h-11 bg-white border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all font-mono text-sm"
              />
              <p class="text-xs text-gray-400">ä¾å¦ 7 è¡¨ç¤ºå
è®¸ä½¿ç¨è¿?7 å¤©å
åå»ºçè¡¥å½ç ã</p>
            </div>

            <div class="flex items-center justify-between p-4 bg-gray-50 rounded-2xl border border-gray-100">
              <div class="space-y-1">
                <p class="font-medium text-gray-900">è¦æ±è´¦å·è¿ææ¶é´è¦çè®¢åæªæ­¢æ</p>
                <p class="text-xs text-gray-500">ä»
å¨å¼å¯âå¼ºå¶å½å¤©ç âæ¶å¯ç¨ï¼å¦ååç«¯ä¼å¼ºå¶å
³é­ã</p>
              </div>
              <input
                type="checkbox"
                v-model="accountRecoveryRequireExpireCoverDeadline"
                :disabled="!accountRecoveryForceTodayCodes"
                class="w-6 h-6 rounded-md border-gray-300 text-blue-600 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              />
            </div>
          </div>

          <div v-if="accountRecoverySettingsError" class="rounded-xl bg-red-50 p-4 text-red-600 border border-red-100 text-sm font-medium">
            {{ accountRecoverySettingsError }}
          </div>

          <div v-if="accountRecoverySettingsSuccess" class="rounded-xl bg-green-50 p-4 text-green-600 border border-green-100 text-sm font-medium">
            {{ accountRecoverySettingsSuccess }}
          </div>

          <div class="flex flex-col sm:flex-row gap-3">
            <Button
              type="button"
              variant="outline"
              class="w-full sm:w-auto h-11 px-4 border-gray-200 rounded-xl"
              @click="loadAccountRecoverySettings"
            >
              å·æ°
            </Button>
            <Button
              type="button"
              :disabled="accountRecoverySettingsLoading"
              class="w-full h-11 rounded-xl bg-black hover:bg-gray-800 text-white shadow-lg shadow-black/5"
              @click="saveAccountRecoverySettings"
            >
              {{ accountRecoverySettingsLoading ? 'ä¿å­ä¸?..' : 'ä¿å­è¡¥å½è®¾ç½®' }}
            </Button>
          </div>
        </CardContent>
      </Card>

            </template>

            <template v-if="settingsSubTab === 'security'">
            <!-- æ¸ éç®¡ç -->
      <Card v-if="isSuperAdmin" class="bg-white rounded-[32px] border border-gray-100 shadow-sm overflow-hidden flex flex-col lg:col-span-2">
        <CardHeader class="border-b border-gray-50 bg-gray-50/30 px-6 py-5 sm:px-8 sm:py-6">
          <CardTitle class="text-xl font-bold text-gray-900">æ¸ éç®¡ç</CardTitle>
          <CardDescription class="text-gray-500">
            æ°å¢/åç¨æ¸ éï¼å¹¶é
ç½®æ¯å¦å
è®¸åééç¨ç ä¸åä¸ä¸æ¸¸å®ç åºå­ï¼æ°å¢æ¸ éé»è®¤ä½¿ç¨éç¨å
æ¢é¡µï¼/redeem/&lt;key&gt;ï¼ã?
          </CardDescription>
        </CardHeader>
        <CardContent class="p-6 sm:p-8 space-y-5 flex-1">
          <div class="flex flex-col sm:flex-row gap-3">
            <Button type="button" variant="outline" class="w-full sm:w-auto h-11 px-4 border-gray-200 rounded-xl" :disabled="channelsLoading" @click="loadChannels">
              {{ channelsLoading ? 'å è½½ä¸?..' : 'å·æ°' }}
            </Button>
            <Button type="button" class="w-full h-11 rounded-xl bg-black hover:bg-gray-800 text-white shadow-lg shadow-black/5" @click="openCreateChannelDialog">
              æ°å¢æ¸ é
            </Button>
          </div>

          <div v-if="channelsError" class="rounded-xl bg-red-50 p-4 text-red-600 border border-red-100 text-sm font-medium">
            {{ channelsError }}
          </div>
          <div v-if="channelsSuccess" class="rounded-xl bg-green-50 p-4 text-green-600 border border-green-100 text-sm font-medium">
            {{ channelsSuccess }}
          </div>

          <div class="overflow-x-auto border border-gray-100 rounded-2xl">
            <table class="min-w-full text-sm">
              <thead class="bg-gray-50">
                <tr class="text-left text-gray-500">
                  <th class="px-4 py-3 font-semibold">Key</th>
                  <th class="px-4 py-3 font-semibold">åç§°</th>
                  <th class="px-4 py-3 font-semibold">æ¨¡å¼</th>
                  <th class="px-4 py-3 font-semibold">Provider</th>
                  <th class="px-4 py-3 font-semibold">åééç¨ç ?/th>
                  <th class="px-4 py-3 font-semibold">ä¸æ¸¸å®ç </th>
                  <th class="px-4 py-3 font-semibold">ç¶æ?/th>
                  <th class="px-4 py-3 font-semibold">å
æ¢é¾æ¥</th>
                  <th class="px-4 py-3 font-semibold text-right">æä½</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="channel in channels" :key="channel.key" class="border-t border-gray-100">
                  <td class="px-4 py-3 font-mono text-gray-900">{{ channel.key }}</td>
                  <td class="px-4 py-3 text-gray-900">{{ channel.name }}</td>
                  <td class="px-4 py-3 font-mono text-gray-700">{{ channel.redeemMode }}</td>
                  <td class="px-4 py-3 font-mono text-gray-700">{{ channel.providerType }}</td>
                  <td class="px-4 py-3">
                    <span class="px-2 py-1 rounded-full text-xs font-medium" :class="channel.allowCommonFallback ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-600'">
                      {{ channel.allowCommonFallback ? 'å
è®¸' : 'ä¸å
è®? }}
                    </span>
                  </td>
                  <td class="px-4 py-3">
                    <span class="px-2 py-1 rounded-full text-xs font-medium" :class="channel.allowDownstreamSale ? 'bg-emerald-50 text-emerald-700' : 'bg-gray-100 text-gray-600'">
                      {{ channel.allowDownstreamSale ? 'åä¸å
±äº«åºå­' : 'ä¸åä¸? }}
                    </span>
                  </td>
                  <td class="px-4 py-3">
                    <span class="px-2 py-1 rounded-full text-xs font-medium" :class="channel.isActive ? 'bg-blue-50 text-blue-700' : 'bg-amber-50 text-amber-700'">
                      {{ channel.isActive ? 'å¯ç¨' : 'åç¨' }}
                    </span>
                  </td>
                  <td class="px-4 py-3 font-mono text-gray-700">/redeem/{{ channel.key }}</td>
                  <td class="px-4 py-3">
                    <div class="flex items-center justify-end gap-2">
                      <Button type="button" variant="outline" class="h-9 px-3 border-gray-200 rounded-xl" @click="openEditChannelDialog(channel)">
                        ç¼è¾
                      </Button>
                      <Button type="button" variant="outline" class="h-9 px-3 border-gray-200 rounded-xl" @click="toggleChannelActive(channel)">
                        {{ channel.isActive ? 'åç¨' : 'å¯ç¨' }}
                      </Button>
                      <Button v-if="!channel.isBuiltin" type="button" variant="outline" class="h-9 px-3 border-red-200 text-red-600 hover:bg-red-50 hover:text-red-700 rounded-xl" @click="deleteChannel(channel)">
                        å é¤
                      </Button>
                    </div>
                  </td>
                </tr>
                <tr v-if="!channels.length">
                  <td colspan="9" class="px-4 py-6 text-center text-gray-400">ææ æ¸ éæ°æ®</td>
                </tr>
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Card v-if="isSuperAdmin" class="bg-white rounded-[32px] border border-gray-100 shadow-sm overflow-hidden flex flex-col lg:col-span-2">
        <CardHeader class="border-b border-gray-50 bg-gray-50/30 px-6 py-5 sm:px-8 sm:py-6">
          <CardTitle class="text-xl font-bold text-gray-900">å
¨å±ä»£çé
ç½®</CardTitle>
          <!-- <CardDescription class="text-gray-500">ç»ä¸é
ç½® `OPEN_ACCOUNTS_SWEEPER_PROXY_URLS`ï¼æ¯ä¸ªä»£çåç¬ç¼è¾ï¼å¹¶å¨åä¸å¤éä¸ªæµè¯ chatgpt.com è¿éæ§ã</CardDescription> -->
        </CardHeader>
        <CardContent class="p-6 sm:p-8 space-y-6 flex-1">
          <div class="rounded-2xl border border-gray-100 bg-gray-50/60 p-4">
            <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <!-- <div class="space-y-1">
                <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">OPEN_ACCOUNTS_SWEEPER_PROXY_URLS</Label>
                <p class="text-sm text-gray-600">é
ç½®åè¿éæ§æµè¯æ¾å¨ä¸èµ·ï¼ä¿å­åå
¥ç³»ç»è®¾ç½®ï¼æµè¯ç´æ¥ä½¿ç¨å½åé¡µé¢éçèç¨¿ã</p>
              </div> -->
              <div class="flex flex-wrap items-center gap-2 text-xs text-gray-500">
                <span class="rounded-full bg-white px-3 py-1.5 border border-gray-200">å·²å¡«å?{{ proxyDraftCount }} è¡?/span>
                <span class="rounded-full bg-white px-3 py-1.5 border border-gray-200">å½åææ {{ proxyEffectiveCount }} æ?/span>
                <!-- <span class="rounded-full bg-white px-3 py-1.5 border border-gray-200">{{ proxyStored ? 'æ¥æºï¼ç³»ç»è®¾ç½? : 'æ¥æºï¼ç¯å¢åéåéææªé
ç½®' }}</span> -->
              </div>
            </div>
          </div>

          <div v-if="proxyError" class="rounded-xl bg-red-50 p-4 text-red-600 border border-red-100 text-sm font-medium">
            {{ proxyError }}
          </div>

          <div v-if="proxySuccess" class="rounded-xl bg-green-50 p-4 text-green-600 border border-green-100 text-sm font-medium">
            {{ proxySuccess }}
          </div>

          <div class="rounded-2xl border border-gray-100 bg-gray-50/60 p-4 space-y-4">
            <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p class="text-sm font-semibold text-gray-900">ä»£çåè¡¨</p>
                <!-- <p class="text-xs text-gray-500">ä¸è¡ä¸ä¸ªä»£çï¼å¯æ°å¢ãå é¤ï¼æµè¯ç»æä¼ç´æ¥è´´å¨å¯¹åºé£ä¸è¡ã</p> -->
              </div>
              <div class="flex flex-wrap items-center gap-2 text-xs text-gray-500">
                <span class="rounded-full bg-white px-3 py-1.5 border border-gray-200">æ»æ° {{ proxyTestTotal }}</span>
                <span class="rounded-full bg-green-50 px-3 py-1.5 border border-green-100 text-green-700">éè¿ {{ proxyTestPassed }}</span>
                <span class="rounded-full bg-red-50 px-3 py-1.5 border border-red-100 text-red-700">å¤±è´¥ {{ proxyTestFailed }}</span>
                <Button
                  type="button"
                  variant="outline"
                  class="h-9 rounded-xl border-gray-200 bg-white px-3"
                  :disabled="proxyLoading || proxyTesting"
                  @click="addProxyRow"
                >
                  <Plus class="mr-2 h-4 w-4" />
                  æ°å¢ä»£ç
                </Button>
              </div>
            </div>

            <div class="space-y-3">
              <div
                v-for="(row, index) in proxyRows"
                :key="row.id"
                class="rounded-2xl border border-gray-200 bg-white/90 p-4"
              >
                <div class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                  <div
                    class="min-w-0 flex-1 space-y-3"
                  >
                    <div class="flex flex-wrap items-center gap-2">
                      <p class="font-medium text-gray-900">ä»£ç {{ index + 1 }}</p>
                      <template v-if="getProxyRowResult(row.value)">
                        <span
                          class="shrink-0 inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium"
                          :class="getProxyRowResult(row.value)?.ok ? 'bg-green-100 text-green-700' : (getProxyRowResult(row.value)?.reachable ? 'bg-orange-100 text-orange-700' : 'bg-red-100 text-red-700')"
                        >
                          {{ getProxyRowResult(row.value)?.ok ? 'éè¿' : (getProxyRowResult(row.value)?.reachable ? 'åé' : 'å¤±è´¥') }}
                        </span>
                        <span class="text-xs text-gray-500">HTTP {{ getProxyRowResult(row.value)?.status || '-' }}</span>
                        <span class="text-xs text-gray-500">{{ getProxyRowResult(row.value)?.durationMs }} ms</span>
                      </template>
                      <span
                        v-else-if="proxyTesting && row.value.trim()"
                        class="shrink-0 inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-700"
                      >
                        æµè¯ä¸?
                      </span>
                      <span
                        v-else-if="row.value.trim()"
                        class="shrink-0 inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-500"
                      >
                        æªæµè¯?
                      </span>
                      <span
                        v-else
                        class="shrink-0 inline-flex items-center rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700"
                      >
                        å¾
å¡«å?
                      </span>
                    </div>

                    <Input
                      v-model="row.value"
                      type="text"
                      placeholder="socks5h://127.0.0.1:1080 æ?http://user:pass@127.0.0.1:8080"
                      class="h-11 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all font-mono text-sm"
                      :disabled="proxyLoading || proxyTesting"
                    />

                    <p v-if="getProxyRowResult(row.value)" class="text-xs break-all" :class="getProxyRowResult(row.value)?.ok ? 'text-green-700' : (getProxyRowResult(row.value)?.reachable ? 'text-orange-700' : 'text-red-700')">
                      {{ getProxyRowResult(row.value)?.message }}
                    </p>
                    <!-- <p v-else class="text-xs text-gray-400">æ¯æ `http`ã`https`ã`socks4`ã`socks4a`ã`socks5`ã`socks5h`ã</p> -->
                    <p v-if="getProxyRowResult(row.value)?.bodySnippet" class="text-[12px] text-gray-500 break-all">
                      {{ getProxyRowResult(row.value)?.bodySnippet }}
                    </p>
                  </div>

                  <Button
                    type="button"
                    variant="outline"
                    class="h-9 rounded-xl px-3 text-gray-600"
                    :disabled="proxyLoading || proxyTesting"
                    @click="removeProxyRow(index)"
                  >
                    <Trash2 class="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </div>
          </div>

          <div class="flex flex-col sm:flex-row gap-3">
            <Button
              type="button"
              variant="outline"
              class="w-full sm:w-auto h-11 rounded-xl"
              :disabled="proxyLoading || proxyTesting"
              @click="loadProxySettings"
            >
              å·æ°
            </Button>
            <Button
              type="button"
              variant="outline"
              class="w-full sm:w-auto h-11 rounded-xl border-gray-200"
              :disabled="proxyLoading || proxyTesting"
              @click="testProxySettings"
            >
              {{ proxyTesting ? 'æµè¯ä¸?..' : 'chatgpt.comè¿éæ§æµè¯? }}
            </Button>
            <Button
              type="button"
              class="w-full sm:flex-1 h-11 rounded-xl bg-black hover:bg-gray-800 text-white shadow-lg shadow-black/5"
              :disabled="proxyLoading || proxyTesting"
              @click="saveProxySettings"
            >
              {{ proxyLoading ? 'ä¿å­ä¸?..' : 'ä¿å­ä»£çé
ç½®' }}
            </Button>
          </div>
        </CardContent>
      </Card>

            </template>

            <template v-if="settingsSubTab === 'billing'">
            <!-- æ¯ä»ååç®¡ç -->
      <Card v-if="isSuperAdmin" class="bg-white rounded-[32px] border border-gray-100 shadow-sm overflow-hidden flex flex-col lg:col-span-2">
        <CardHeader class="border-b border-gray-50 bg-gray-50/30 px-6 py-5 sm:px-8 sm:py-6">
          <CardTitle class="text-xl font-bold text-gray-900">æ¯ä»ååç®¡ç</CardTitle>
          <CardDescription class="text-gray-500">
            é
ç½®ååä»·æ ¼/æå¡æ?è®¢åç±»åä»¥åæ¸ éä¼å
çº§ï¼codeChannelsï¼ï¼ä¸åæ¶ç³»ç»ä¼æä¼å
çº§èªå¨å¹é
æåºå­çæ¸ éå¹¶éå®ã?
          </CardDescription>
        </CardHeader>
        <CardContent class="p-6 sm:p-8 space-y-5 flex-1">
          <div class="flex flex-col sm:flex-row gap-3">
            <Button type="button" variant="outline" class="w-full sm:w-auto h-11 px-4 border-gray-200 rounded-xl" :disabled="purchaseProductsLoading" @click="refreshPurchaseProducts">
              {{ purchaseProductsLoading ? 'å è½½ä¸?..' : 'å·æ°' }}
            </Button>
            <Button type="button" class="w-full h-11 rounded-xl bg-black hover:bg-gray-800 text-white shadow-lg shadow-black/5" @click="openCreatePurchaseProductDialog">
              æ°å¢åå
            </Button>
          </div>

          <div v-if="purchaseProductsError" class="rounded-xl bg-red-50 p-4 text-red-600 border border-red-100 text-sm font-medium">
            {{ purchaseProductsError }}
          </div>
          <div v-if="purchaseProductsSuccess" class="rounded-xl bg-green-50 p-4 text-green-600 border border-green-100 text-sm font-medium">
            {{ purchaseProductsSuccess }}
          </div>

          <div class="overflow-x-auto border border-gray-100 rounded-2xl">
            <table class="min-w-full text-sm">
              <thead class="bg-gray-50">
                <tr class="text-left text-gray-500">
                  <th class="px-4 py-3 font-semibold">Key</th>
                  <th class="px-4 py-3 font-semibold">åç§°</th>
                  <th class="px-4 py-3 font-semibold">ä»·æ ¼</th>
                  <th class="px-4 py-3 font-semibold">æå¡æ?/th>
                  <th class="px-4 py-3 font-semibold">ç±»å</th>
                  <th class="px-4 py-3 font-semibold">æ¸ éç­ç¥</th>
                  <th class="px-4 py-3 font-semibold">åºå­</th>
                  <th class="px-4 py-3 font-semibold">ç¶æ?/th>
                  <th class="px-4 py-3 font-semibold text-right">æä½</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="product in purchaseProducts" :key="product.productKey" class="border-t border-gray-100">
                  <td class="px-4 py-3 font-mono text-gray-900">{{ product.productKey }}</td>
                  <td class="px-4 py-3 text-gray-900">{{ product.productName }}</td>
                  <td class="px-4 py-3 font-mono text-gray-700">Â¥ {{ product.amount }}</td>
                  <td class="px-4 py-3 text-gray-700">{{ product.serviceDays }} å¤?/td>
                  <td class="px-4 py-3">
                    <span class="px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-700">{{ product.orderType }}</span>
                  </td>
                  <td class="px-4 py-3 font-mono text-gray-700">{{ product.codeChannels }}</td>
                  <td class="px-4 py-3 font-mono text-gray-700">{{ purchaseAvailability[product.productKey] ?? '-' }}</td>
                  <td class="px-4 py-3">
                    <span class="px-2 py-1 rounded-full text-xs font-medium" :class="product.isActive ? 'bg-blue-50 text-blue-700' : 'bg-amber-50 text-amber-700'">
                      {{ product.isActive ? 'ä¸æ¶' : 'ä¸æ¶' }}
                    </span>
                  </td>
                  <td class="px-4 py-3">
                    <div class="flex items-center justify-end gap-2">
                      <Button type="button" variant="outline" class="h-9 px-3 border-gray-200 rounded-xl" @click="openEditPurchaseProductDialog(product)">
                        ç¼è¾
                      </Button>
                      <Button type="button" variant="outline" class="h-9 px-3 border-gray-200 rounded-xl" @click="togglePurchaseProductActive(product)">
                        {{ product.isActive ? 'åç¨' : 'å¯ç¨' }}
                      </Button>
                      <Button type="button" variant="outline" class="h-9 px-3 border-red-200 text-red-600 hover:bg-red-50 hover:text-red-700 rounded-xl" @click="deletePurchaseProduct(product)">
                        å é¤
                      </Button>
                    </div>
                  </td>
                </tr>
                <tr v-if="!purchaseProducts.length">
                  <td colspan="9" class="px-4 py-6 text-center text-gray-400">ææ ååæ°æ®</td>
                </tr>
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Card v-if="isSuperAdmin" class="bg-white rounded-[32px] border border-gray-100 shadow-sm overflow-hidden flex flex-col lg:col-span-2">
        <CardHeader class="border-b border-gray-50 bg-gray-50/30 px-6 py-5 sm:px-8 sm:py-6">
          <CardTitle class="text-xl font-bold text-gray-900">ä¸æ¸¸å®ç é
ç½®</CardTitle>
          <CardDescription class="text-gray-500">
            ä¸æ¸¸å
¬å¼é¡µåºå®ä¸º <span class="font-mono text-gray-700">/downstream</span>ï¼åºå­èªå¨å¤ç¨ææå¼å¯âä¸æ¸¸å®ç âçæ¸ éå
±äº«åºå­ã?
          </CardDescription>
        </CardHeader>
        <CardContent class="p-6 sm:p-8 space-y-6 flex-1">
          <div class="flex items-center justify-between rounded-2xl border border-gray-100 bg-gray-50 p-4">
            <div class="space-y-1">
              <p class="font-medium text-gray-900">å¯ç¨ä¸æ¸¸å
¬å¼å®ç é¡</p>
              <p class="text-xs text-gray-500">å
³é­åï¼/downstream ä»
è¿åæªå¯ç¨ç¶æï¼ä¸åæ¥åæ°ä¸åã</p>
            </div>
            <input
              v-model="downstreamSaleEnabled"
              type="checkbox"
              class="w-6 h-6 rounded-md border-gray-300 text-blue-600 focus:ring-blue-500"
            />
          </div>

          <div class="grid gap-4 lg:grid-cols-2">
            <div class="space-y-2">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">åååç§°</Label>
              <Input
                v-model="downstreamSaleProductName"
                type="text"
                placeholder="ä¸æ¸¸æ¸ éå
æ¢ç ?
                class="h-11 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all"
                :disabled="downstreamSaleLoading"
              />
            </div>
            <div class="space-y-2">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">ç»ä¸å®ä»·ï¼å
ï¼</Label>
              <Input
                v-model="downstreamSaleAmount"
                type="text"
                placeholder="9.90"
                class="h-11 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all font-mono"
                :disabled="downstreamSaleLoading"
              />
            </div>
          </div>

          <div class="grid gap-3 sm:grid-cols-2">
            <label class="flex items-center justify-between rounded-2xl border border-gray-100 bg-gray-50 p-4">
              <div class="space-y-1">
                <p class="font-medium text-gray-900">æ¯ä»å®</p>
                <p class="text-xs text-gray-500">ä¸æ¸¸é¡µå±ç¤ºæ¯ä»å®æ¯ä»</p>
              </div>
              <input
                v-model="downstreamSalePayAlipayEnabled"
                type="checkbox"
                class="w-5 h-5 rounded-md border-gray-300 text-blue-600 focus:ring-blue-500"
              />
            </label>

            <label class="flex items-center justify-between rounded-2xl border border-gray-100 bg-gray-50 p-4">
              <div class="space-y-1">
                <p class="font-medium text-gray-900">å¾®ä¿¡æ¯ä»</p>
                <p class="text-xs text-gray-500">ä¸æ¸¸é¡µå±ç¤ºå¾®ä¿¡æ¯ä»</p>
              </div>
              <input
                v-model="downstreamSalePayWxpayEnabled"
                type="checkbox"
                class="w-5 h-5 rounded-md border-gray-300 text-blue-600 focus:ring-blue-500"
              />
            </label>
          </div>

          <div class="rounded-2xl border border-emerald-100 bg-emerald-50/70 p-4 text-sm text-emerald-900">
            ä¸æ¸¸é¡µä¼æè¿éçé
ç½®å¨æå±ç¤ºæ¯ä»æ¹å¼ï¼æ¯ä»å®åå¾®ä¿¡è³å°ä¿çä¸ä¸ªã?
          </div>

          <div v-if="downstreamSaleError" class="rounded-xl bg-red-50 p-4 text-red-600 border border-red-100 text-sm font-medium">
            {{ downstreamSaleError }}
          </div>

          <div v-if="downstreamSaleSuccess" class="rounded-xl bg-green-50 p-4 text-green-600 border border-green-100 text-sm font-medium">
            {{ downstreamSaleSuccess }}
          </div>

          <div class="flex flex-col sm:flex-row gap-3">
            <Button
              type="button"
              variant="outline"
              class="w-full sm:w-auto h-11 rounded-xl"
              :disabled="downstreamSaleLoading"
              @click="loadDownstreamSaleSettings"
            >
              å·æ°
            </Button>
            <Button
              type="button"
              class="w-full sm:flex-1 h-11 rounded-xl bg-black hover:bg-gray-800 text-white shadow-lg shadow-black/5"
              :disabled="downstreamSaleLoading"
              @click="saveDownstreamSaleSettings"
            >
              {{ downstreamSaleLoading ? 'ä¿å­ä¸?..' : 'ä¿å­ä¸æ¸¸å®ç é
ç½®' }}
            </Button>
          </div>
        </CardContent>
      </Card>

            </template>

            <template v-if="settingsSubTab === 'notifications'">
            <!-- SMTP / ç¬¬ä¸æ¹é
ç½?-->
      <Card v-if="isSuperAdmin" class="bg-white rounded-[32px] border border-gray-100 shadow-sm overflow-hidden flex flex-col lg:col-span-2">
        <CardHeader class="border-b border-gray-50 bg-gray-50/30 px-6 py-5 sm:px-8 sm:py-6">
          <CardTitle class="text-xl font-bold text-gray-900">SMTP é®ä»¶åè­¦é
ç½®</CardTitle>
          <CardDescription class="text-gray-500">ç¨äºåééªè¯ç /è®¢åé®ä»¶/ç³»ç»åè­¦é®ä»¶ï¼ä¿å­åå®æ¶çæï¼ã</CardDescription>
        </CardHeader>
        <CardContent class="p-6 sm:p-8 space-y-6 flex-1">
          <div class="grid gap-4 lg:grid-cols-3">
            <div class="space-y-2">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">SMTP Host</Label>
              <Input
                v-model="smtpHost"
                type="text"
                placeholder="smtp.example.com"
                class="h-11 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all font-mono text-sm"
                :disabled="smtpLoading"
              />
            </div>
            <div class="space-y-2">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">ç«¯å£</Label>
              <Input
                v-model="smtpPort"
                type="text"
                placeholder="465"
                class="h-11 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all font-mono text-sm"
                :disabled="smtpLoading"
              />
            </div>
            <div class="space-y-2">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">å®å
¨è¿æ¥</Label>
              <Select v-model="smtpSecure" :disabled="smtpLoading">
                <SelectTrigger class="h-11 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all">
                  <SelectValue placeholder="éæ©" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="true">å¯ç¨ TLS/SSL</SelectItem>
                  <SelectItem value="false">ä¸å¯ç?TLS/SSL</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div class="grid gap-4 lg:grid-cols-3">
            <div class="space-y-2">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">ç¨æ·å</Label>
              <Input
                v-model="smtpUser"
                type="text"
                placeholder="bot@example.com"
                class="h-11 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all font-mono text-sm"
                :disabled="smtpLoading"
              />
            </div>
            <div class="space-y-2">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">å¯ç </Label>
              <div class="relative">
                <Input
                  v-model="smtpPass"
                  :type="showSmtpPass ? 'text' : 'password'"
                  placeholder="çç©ºè¡¨ç¤ºä¸ä¿®æ?
                  class="h-11 pr-10 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all font-mono text-sm"
                  :disabled="smtpLoading"
                />
                <button
                  type="button"
                  @click="toggleShowSmtpPass"
                  class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                >
                  <EyeOff v-if="showSmtpPass" class="h-4 w-4" />
                  <Eye v-else class="h-4 w-4" />
                </button>
              </div>
              <p class="text-xs text-gray-400">
                <template v-if="smtpPassStored">å¯ç å·²å
¥åºï¼çç©ºè¡¨ç¤ºä¸ä¿®æ¹ã?/template>
                <template v-else-if="smtpPassSet">å½åå¯ç æªå
¥åºï¼ä¿å­æ¶å¯èªå¨ä»?.env è¿ç§»æå¨æ­¤éæ°å¡«åã?/template>
                <template v-else>æªè®¾ç½®å¯ç ã?/template>
              </p>
            </div>
            <div class="space-y-2">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">åä»¶äº?From</Label>
              <Input
                v-model="smtpFrom"
                type="text"
                placeholder="çç©ºåä½¿ç?SMTP_USER"
                class="h-11 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all text-sm"
                :disabled="smtpLoading"
              />
            </div>
          </div>

          <div class="space-y-2">
            <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">åè­¦æ¶ä»¶äººï¼ADMIN_ALERT_EMAILï¼</Label>
            <Input
              v-model="adminAlertEmail"
              type="text"
              placeholder="admin@example.com,ops@example.com"
              class="h-11 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all font-mono text-sm"
              :disabled="smtpLoading"
            />
            <p class="text-xs text-gray-400">å¤ä¸ªæ¶ä»¶äººç¨éå·åéï¼çç©ºåä¸åéç³»ç»åè­¦é®ä»¶ã</p>
          </div>

          <div v-if="smtpError" class="rounded-xl bg-red-50 p-4 text-red-600 border border-red-100 text-sm font-medium">
            {{ smtpError }}
          </div>

          <div v-if="smtpSuccess" class="rounded-xl bg-green-50 p-4 text-green-600 border border-green-100 text-sm font-medium">
            {{ smtpSuccess }}
          </div>

          <div class="flex flex-col sm:flex-row gap-3">
            <Button
              type="button"
              variant="outline"
              class="w-full sm:w-auto h-11 rounded-xl"
              :disabled="smtpLoading"
              @click="loadSmtpSettings"
            >
              å·æ°
            </Button>
            <Button
              type="button"
              class="w-full sm:flex-1 h-11 rounded-xl bg-black hover:bg-gray-800 text-white shadow-lg shadow-black/5"
              :disabled="smtpLoading"
              @click="saveSmtpSettings"
            >
              {{ smtpLoading ? 'ä¿å­ä¸?..' : 'ä¿å­ SMTP é
ç½®' }}
            </Button>
          </div>
        </CardContent>
      </Card>
      </template>

      <template v-if="settingsSubTab === 'integrations'">
      <!-- Linux DO OAuth é
ç½® -->
      <Card v-if="isSuperAdmin" class="bg-white rounded-[32px] border border-gray-100 shadow-sm overflow-hidden flex flex-col lg:col-span-2">
        <CardHeader class="border-b border-gray-50 bg-gray-50/30 px-6 py-5 sm:px-8 sm:py-6">
          <CardTitle class="text-xl font-bold text-gray-900">Linux DO OAuth é
ç½®</CardTitle>
          <CardDescription class="text-gray-500">ç¨äº Linux DO ç»å½/ææï¼ä¿å­åå®æ¶çæï¼ã</CardDescription>
        </CardHeader>
        <CardContent class="p-6 sm:p-8 space-y-6 flex-1">
          <div class="grid gap-4">
            <div class="space-y-2">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Client ID</Label>
              <Input
                v-model="linuxdoClientId"
                type="text"
                placeholder="Linux DO Client ID"
                class="h-11 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all font-mono text-sm"
                :disabled="linuxdoOauthLoading"
              />
            </div>
            <div class="space-y-2">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Client Secret</Label>
              <div class="relative">
                <Input
                  v-model="linuxdoClientSecret"
                  :type="showLinuxdoClientSecret ? 'text' : 'password'"
                  placeholder="çç©ºè¡¨ç¤ºä¸ä¿®æ?
                  class="h-11 pr-10 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all font-mono text-sm"
                  :disabled="linuxdoOauthLoading"
                />
                <button
                  type="button"
                  @click="toggleShowLinuxdoClientSecret"
                  class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                >
                  <EyeOff v-if="showLinuxdoClientSecret" class="h-4 w-4" />
                  <Eye v-else class="h-4 w-4" />
                </button>
              </div>
              <p class="text-xs text-gray-400">
                <template v-if="linuxdoClientSecretStored">Client Secret å·²å
¥åºï¼çç©ºè¡¨ç¤ºä¸ä¿®æ¹ã?/template>
                <template v-else-if="linuxdoClientSecretSet">Client Secret æªå
¥åºï¼ä¿å­æ¶å¯ä»?.env èªå¨è¿ç§»æå¨æ­¤éæ°å¡«åã?/template>
                <template v-else>æªè®¾ç½?Client Secretã?/template>
              </p>
            </div>
            <div class="space-y-2">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Redirect URI</Label>
              <Input
                v-model="linuxdoRedirectUri"
                type="text"
                placeholder="https://example.com/redeem/linux-do"
                class="h-11 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all text-sm font-mono"
                :disabled="linuxdoOauthLoading"
              />
            </div>
          </div>

          <div v-if="linuxdoOauthError" class="rounded-xl bg-red-50 p-4 text-red-600 border border-red-100 text-sm font-medium">
            {{ linuxdoOauthError }}
          </div>

          <div v-if="linuxdoOauthSuccess" class="rounded-xl bg-green-50 p-4 text-green-600 border border-green-100 text-sm font-medium">
            {{ linuxdoOauthSuccess }}
          </div>

          <div class="flex flex-col sm:flex-row gap-3">
            <Button
              type="button"
              variant="outline"
              class="w-full sm:w-auto h-11 rounded-xl"
              :disabled="linuxdoOauthLoading"
              @click="loadLinuxDoOAuthSettings"
            >
              å·æ°
            </Button>
            <Button
              type="button"
              class="w-full sm:flex-1 h-11 rounded-xl bg-black hover:bg-gray-800 text-white shadow-lg shadow-black/5"
              :disabled="linuxdoOauthLoading"
              @click="saveLinuxDoOAuthSettings"
            >
              {{ linuxdoOauthLoading ? 'ä¿å­ä¸?..' : 'ä¿å­ Linux DO OAuth é
ç½®' }}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card v-if="isSuperAdmin" class="bg-white rounded-[32px] border border-gray-100 shadow-sm overflow-hidden flex flex-col lg:col-span-2">
        <CardHeader class="border-b border-gray-50 bg-gray-50/30 px-6 py-5 sm:px-8 sm:py-6">
          <CardTitle class="text-xl font-bold text-gray-900">Linux DO Credit é
ç½®</CardTitle>
          <CardDescription class="text-gray-500">ç¨äº Credit ç§¯åæ¯ä»/åè°éªç­¾ï¼ä¿å­åå®æ¶çæï¼ã</CardDescription>
        </CardHeader>
        <CardContent class="p-6 sm:p-8 space-y-6 flex-1">
          <div class="grid gap-4 lg:grid-cols-2">
            <div class="space-y-2">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">PID</Label>
              <Input
                v-model="linuxdoCreditPid"
                type="text"
                placeholder="Credit PID"
                class="h-11 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all font-mono text-sm"
                :disabled="linuxdoCreditLoading"
              />
            </div>
            <div class="space-y-2">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">KEY</Label>
              <div class="relative">
                <Input
                  v-model="linuxdoCreditKey"
                  :type="showLinuxdoCreditKey ? 'text' : 'password'"
                  placeholder="çç©ºè¡¨ç¤ºä¸ä¿®æ?
                  class="h-11 pr-10 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all font-mono text-sm"
                  :disabled="linuxdoCreditLoading"
                />
                <button
                  type="button"
                  @click="toggleShowLinuxdoCreditKey"
                  class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                >
                  <EyeOff v-if="showLinuxdoCreditKey" class="h-4 w-4" />
                  <Eye v-else class="h-4 w-4" />
                </button>
              </div>
              <p class="text-xs text-gray-400">
                <template v-if="linuxdoCreditKeyStored">KEY å·²å
¥åºï¼çç©ºè¡¨ç¤ºä¸ä¿®æ¹ã?/template>
                <template v-else-if="linuxdoCreditKeySet">KEY æªå
¥åºï¼ä¿å­æ¶å¯ä»?.env èªå¨è¿ç§»æå¨æ­¤éæ°å¡«åã?/template>
                <template v-else>æªè®¾ç½?KEYã?/template>
              </p>
            </div>
          </div>

          <div v-if="linuxdoCreditError" class="rounded-xl bg-red-50 p-4 text-red-600 border border-red-100 text-sm font-medium">
            {{ linuxdoCreditError }}
          </div>

          <div v-if="linuxdoCreditSuccess" class="rounded-xl bg-green-50 p-4 text-green-600 border border-green-100 text-sm font-medium">
            {{ linuxdoCreditSuccess }}
          </div>

          <div class="flex flex-col sm:flex-row gap-3">
            <Button
              type="button"
              variant="outline"
              class="w-full sm:w-auto h-11 rounded-xl"
              :disabled="linuxdoCreditLoading"
              @click="loadLinuxDoCreditSettings"
            >
              å·æ°
            </Button>
            <Button
              type="button"
              class="w-full sm:flex-1 h-11 rounded-xl bg-black hover:bg-gray-800 text-white shadow-lg shadow-black/5"
              :disabled="linuxdoCreditLoading"
              @click="saveLinuxDoCreditSettings"
            >
              {{ linuxdoCreditLoading ? 'ä¿å­ä¸?..' : 'ä¿å­ Linux DO Credit é
ç½®' }}
            </Button>
          </div>
        </CardContent>
      </Card>

      </template>

      <template v-if="settingsSubTab === 'upstream'">
      <Card v-if="isSuperAdmin" class="bg-white rounded-[32px] border border-gray-100 shadow-sm overflow-hidden flex flex-col lg:col-span-2">
        <CardHeader class="border-b border-gray-50 bg-gray-50/30 px-6 py-5 sm:px-8 sm:py-6">
          <CardTitle class="text-xl font-bold text-gray-900">ä¸ä¸æ¸¸æ¥å£é
ç½</CardTitle>
          <CardDescription class="text-gray-500">åºç«ç¨äºæå¡å¯æäº¤å°ä¸æ¸¸å¹³å°ï¼å
¥ç«ç¨äºè®©ä¸åä¸æ¸¸å®ä¾éè¿æ åæ¥å£è°ç¨å½åå¹³å°ï¼ä¸æ¸¸æ å°ç ä¹èµ°è¿å¥å
¥ç«æ¥å£ã</CardDescription>
        </CardHeader>
        <CardContent class="p-6 sm:p-8 space-y-6 flex-1">
          <div class="rounded-2xl border border-gray-200 bg-gray-50/70 p-4 space-y-3">
            <div class="flex items-center gap-2">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">æ¬ç«åå</Label>
              <InfoTooltip content="ä¿å­åä¼åæ¶ç¨äºå¹³å°éç¨æ¥å£åºç«æ¶èªå¨æºå¸¦ä¸æ¸¸ååï¼ä»¥åæ¯ä»/å¼æ¾è´¦å·ç¸å
³åè°å°åçæãçç©ºåç»§ç»­æè¯·æ±æç¯å¢åéèªå¨æ¨å¯¼ã? width-class="w-96" />
            </div>
            <Input
              v-model="upstreamPublicBaseUrl"
              type="text"
              placeholder="https://example.com"
              class="h-11 bg-white border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all font-mono text-sm"
              :disabled="upstreamLoading"
            />
          </div>

          <Tabs v-model="upstreamConfigTab" class="space-y-6">
            <div class="rounded-2xl border border-gray-200 bg-gray-50/80 p-2">
              <TabsList class="grid h-auto w-full grid-cols-2 gap-2 bg-transparent p-0">
                <TabsTrigger value="outbound" class="rounded-xl px-4 py-3">åºç«å±¥çº¦</TabsTrigger>
                <TabsTrigger value="inbound" class="rounded-xl px-4 py-3">å
¥ç«æ¥å£</TabsTrigger>
              </TabsList>
            </div>

            <TabsContent value="outbound" class="mt-0 space-y-6">
              <div class="rounded-2xl border border-blue-100 bg-blue-50/60 p-4 text-sm text-blue-900">
                <div class="flex items-start gap-2">
                  <div class="mt-0.5 h-2.5 w-2.5 rounded-full bg-blue-500"></div>
                  <div class="space-y-1">
                    <p class="font-semibold">åºç«å±¥çº¦ä¼å¨å
æ¢ææ¯ä»æååè§¦åã</p>
                  </div>
                </div>
              </div>

              <div class="grid gap-4 lg:grid-cols-2">
                <div class="space-y-2">
                  <div class="flex items-center gap-2">
                    <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">åºç«å±¥çº¦å¼å
</Label>
                    <InfoTooltip content="å
³é­åï¼ææ?external-card æ¸ éé½ä¸ä¼åå¤é¨ç³»ç»åèµ·è¯·æ±ã? width-class="w-64" />
                  </div>
                  <Select v-model="upstreamProviderEnabled" :disabled="upstreamLoading">
                    <SelectTrigger class="h-11 bg-gray-50 border-gray-200 rounded-xl">
                      <SelectValue placeholder="éæ©ç¶æ? />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="true">å¯ç¨</SelectItem>
                      <SelectItem value="false">ç¦ç¨</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div class="space-y-2">
                  <div class="flex items-center gap-2">
                    <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Provider ç±»å</Label>
                    <InfoTooltip content="èªå®ä¹æ¥å£éåä»»æç¬¬ä¸æ?JSON æ¥å£ï¼å¹³å°éç¨æ¥å£éååé¡¹ç®å®ä¾ä¹é´å¯¹æ¥ï¼åºå®è°ç¨ /api/upstream/cards/redeemã? width-class="w-72" />
                  </div>
                  <Select v-model="upstreamProviderType" :disabled="upstreamLoading">
                    <SelectTrigger class="h-11 bg-gray-50 border-gray-200 rounded-xl">
                      <SelectValue placeholder="éæ© Provider" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="custom-http">èªå®ä¹æ¥å?/SelectItem>
                      <SelectItem value="platform-upstream">å¹³å°éç¨æ¥å£</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div class="grid gap-4 lg:grid-cols-2">
                <div class="space-y-2">
                  <div class="flex items-center gap-2">
                    <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">ä¾åºååç§</Label>
                    <InfoTooltip content="ä»
ç¨äºåå°è¯å«æ¥æºï¼ç¨æ·åå°ä¸ä¼å±ç¤ºè¿ä¸ªåå­ã? width-class="w-60" />
                  </div>
                  <Input
                    v-model="upstreamSupplierName"
                    type="text"
                    placeholder="ä¾å¦ï¼ä¾åºå A"
                    class="h-11 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all text-sm"
                    :disabled="upstreamLoading"
                  />
                </div>

                <div class="space-y-2">
                  <div class="flex items-center gap-2">
                    <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">è¯·æ±è¶
æ¶ï¼æ¯«ç§ï¼</Label>
                    <InfoTooltip content="å¤é¨æ¥å£è¶
æ¶åæ¬æ¬¡å±¥çº¦ä¼å¤±è´¥ï¼æ¯ä»è®¢åä¼ä¿çä¸ºå·²æ¯ä»æªå¼éï¼å¯å¨ä¿®å¤é
ç½®åéè¿è®¢åå·æ°éè¯ã? width-class="w-80" />
                  </div>
                  <Input
                    v-model="upstreamTimeoutMs"
                    type="text"
                    placeholder="15000"
                    class="h-11 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all font-mono text-sm"
                    :disabled="upstreamLoading"
                  />
                </div>
              </div>

              <div v-if="isCustomUpstreamProvider" class="space-y-4">
                <div class="space-y-2">
                  <div class="flex items-center gap-2">
                    <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">èªå®ä¹æ¥å?URL</Label>
                    <InfoTooltip content="å¡«åå®æ´çè¯·æ±å°åãç³»ç»ä¼ç?POST + application/json è°ç¨è¿éã? width-class="w-64" />
                  </div>
                  <Input
                    v-model="upstreamCustomUrl"
                    type="text"
                    placeholder="https://partner.example.com/api/redeem"
                    class="h-11 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all font-mono text-sm"
                    :disabled="upstreamLoading"
                  />
                </div>

                <div class="space-y-2">
                  <div class="flex items-center gap-2">
                    <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">èªå®ä¹?Body JSON</Label>
                    <InfoTooltip :content="`ç³»ç»ä¼å
æ¿æ¢å ä½ç¬¦ï¼åæ JSON åéã\n${upstreamPlaceholderHelp}`" width-class="w-80" />
                  </div>
                  <textarea
                    v-model="upstreamCustomBodyTemplate"
                    rows="8"
                    placeholder='{"userEmail":"{{email}}","cardCode":"{{code}}"}'
                    class="w-full rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 font-mono text-sm text-gray-900 outline-none transition-all focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                    :disabled="upstreamLoading"
                  ></textarea>
                  <p class="text-xs text-gray-400">
                    {{ upstreamPlaceholderHelp }}
                  </p>
                </div>
              </div>

              <div v-else-if="isPlatformUpstreamProvider" class="space-y-4">
                <div class="grid gap-4 lg:grid-cols-2">
                  <div class="space-y-2">
                    <div class="flex items-center gap-2">
                      <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">å¹³å° Base URL</Label>
                      <InfoTooltip content="å¡«åå¯¹æ¹å¹³å°çæ ¹å°åï¼ç³»ç»ä¼èªå¨æ¼æ¥æ åè·¯å¾ /api/upstream/cards/redeemã? width-class="w-72" />
                    </div>
                    <Input
                      v-model="upstreamBaseUrl"
                      type="text"
                      placeholder="https://partner.example.com"
                      class="h-11 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all font-mono text-sm"
                      :disabled="upstreamLoading"
                    />
                  </div>

                  <div class="space-y-2">
                    <div class="flex items-center gap-2">
                      <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">åºç« API Key</Label>
                      <InfoTooltip content="å¦æå¯¹æ¹å¹³å°å¯ç¨äºå
¥ç«?API å¯é¥ï¼è¿éå¡«åå¯¹åºçåºç«å¯é¥ã? width-class="w-72" />
                    </div>
                    <div class="relative">
                      <Input
                        v-model="upstreamOutboundApiKey"
                        :type="showUpstreamOutboundApiKey ? 'text' : 'password'"
                        placeholder="çç©ºè¡¨ç¤ºä¸ä¿®æ?
                        class="h-11 pr-10 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all font-mono text-sm"
                        :disabled="upstreamLoading"
                      />
                      <button
                        type="button"
                        @click="toggleShowUpstreamOutboundApiKey"
                        class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                      >
                        <EyeOff v-if="showUpstreamOutboundApiKey" class="h-4 w-4" />
                        <Eye v-else class="h-4 w-4" />
                      </button>
                    </div>
                    <p class="text-xs text-gray-400">
                      <template v-if="upstreamOutboundApiKeyStored">å·²å
¥åºï¼çç©ºè¡¨ç¤ºä¸ä¿®æ¹ã?/template>
                      <template v-else-if="upstreamOutboundApiKeySet">å½åå¼å¯ç¨ä½æªå
¥åºï¼ä¿å­æ¶ä¼è¿ç§»æè¦çã?/template>
                      <template v-else>æªè®¾ç½®ã?/template>
                    </p>
                  </div>
                </div>

                <div class="rounded-2xl border border-gray-200 bg-gray-50/70 p-4 text-sm text-gray-600">
                  <p class="font-medium text-gray-900">å¹³å°éç¨æ¥å£åºå®è·¯å¾</p>
                  <div class="mt-2 grid gap-2 md:grid-cols-3">
                    <code class="rounded-lg bg-white px-3 py-2 text-xs text-gray-700 shadow-sm">/api/upstream/health</code>
                    <code class="rounded-lg bg-white px-3 py-2 text-xs text-gray-700 shadow-sm">/api/upstream/cards/check</code>
                    <code class="rounded-lg bg-white px-3 py-2 text-xs text-gray-700 shadow-sm">/api/upstream/cards/redeem</code>
                  </div>
                </div>
              </div>
            </TabsContent>

            <TabsContent value="inbound" class="mt-0 space-y-6">
              <div class="rounded-2xl border border-emerald-100 bg-emerald-50/60 p-4 text-sm text-emerald-900">
                <div class="flex items-start gap-2">
                  <div class="mt-0.5 h-2.5 w-2.5 rounded-full bg-emerald-500"></div>
                  <div class="space-y-1">
                    <p class="font-semibold">å
¥ç«æ¥å£ä¼æå½åå¹³å°æ´é²ææ åä¾åºæ¹ã</p>
                    <p class="text-emerald-800/80">å
¶ä»å¹³å°å¯ä»¥ç¨åºå®è·¯å¾è¯·æ±ä½ çå¡å¯æ¥è¯¢ä¸å
æ¢è½åï¼çå®å
æ¢ç åä¸æ¸¸æ å°ç é½å¯ä»¥éè¿è¿éå
¥ç«å¯¹æ¥ã</p>
                  </div>
                </div>
              </div>

              <div class="space-y-2">
                <div class="flex items-center gap-2">
                  <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">å
¥ç«æ¥å£å¼å
</Label>
                  <InfoTooltip content="å¯ç¨åï¼å¤é¨å¹³å°å¯éè¿æ åè·¯å¾è¯·æ±å½åå¹³å°çå¥åº·æ£æ¥ãå¡å¯æ ¡éªåå¡å¯å
æ¢æ¥å£ã? width-class="w-80" />
                </div>
                <Select v-model="upstreamApiEnabled" :disabled="upstreamLoading">
                  <SelectTrigger class="h-11 bg-gray-50 border-gray-200 rounded-xl">
                    <SelectValue placeholder="éæ©ç¶æ? />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="true">å¯ç¨</SelectItem>
                    <SelectItem value="false">ç¦ç¨</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div class="space-y-4">
                <div class="flex items-center justify-between gap-3">
                  <div>
                    <p class="text-sm font-semibold text-gray-900">ä¸æ¸¸ååä¸å
¥ç«?API Key</p>
                    <p class="text-xs text-gray-500">å»ºè®®æ¯ä¸ªä¸æ¸¸å®ä¾åç¬åé
ä¸æ¡è§åï¼ååæä¸»æºåç²¾ç¡®å¹é
ã</p>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    class="h-10 rounded-xl"
                    :disabled="upstreamLoading"
                    @click="addUpstreamInboundClient"
                  >
                    <Plus class="mr-2 h-4 w-4" />
                    æ°å¢è§å
                  </Button>
                </div>

                <div
                  v-for="(client, index) in upstreamInboundClients"
                  :key="client.id || `upstream-inbound-${index}`"
                  class="rounded-2xl border border-gray-200 bg-gray-50/70 p-4 space-y-4"
                >
                  <div class="flex items-start justify-between gap-3">
                    <div class="space-y-1">
                      <p class="font-medium text-gray-900">ä¸æ¸¸è§å {{ index + 1 }}</p>
                      <p class="text-xs text-gray-500">
                        <template v-if="client.legacy">è¿æ¯æ§å API Key èªå¨è¿ç§»åºæ¥çé»è®¤è§åï¼ä¿å­åä¼è½¬ææ°çå¤ååé
ç½®ã?/template>
                        <template v-else>ååæ¯æå¡«å `partner.example.com` æå®æ?URLï¼ä¿å­æ¶ä¼èªå¨è§èåæä¸»æºåã?/template>
                      </p>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      class="h-9 rounded-xl px-3 text-gray-600"
                      :disabled="upstreamLoading"
                      @click="removeUpstreamInboundClient(index)"
                    >
                      <Trash2 class="h-4 w-4" />
                    </Button>
                  </div>

                  <div class="grid gap-4 lg:grid-cols-2">
                    <div class="space-y-2">
                      <div class="flex items-center gap-2">
                        <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">ä¸æ¸¸åå</Label>
                        <InfoTooltip content="å¡«åä¸æ¸¸å®ä¾èªå·±çè®¿é®ååãçç©ºè¡¨ç¤ºé»è®¤è§åï¼ä¼å¹é
æææ²¡æåç¬é
ç½®çä¸æ¸¸ã? width-class="w-80" />
                      </div>
                      <Input
                        v-model="client.domain"
                        type="text"
                        placeholder="partner.example.com"
                        class="h-11 bg-white border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all font-mono text-sm"
                        :disabled="upstreamLoading"
                      />
                      <p class="text-xs text-gray-400">çç©ºè¡¨ç¤ºé»è®¤è§åï¼æ¨èä¼å
ä¸ºæ¯ä¸ªä¸æ¸¸å®ä¾å¡«åå¯ä¸ååã</p>
                    </div>

                    <div class="space-y-2">
                      <div class="flex items-center gap-2">
                        <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">å
¥ç« API Key</Label>
                        <InfoTooltip content="è¯·æ±æ¹éè¦å¨è¯·æ±å¤´æºå¸?X-Upstream-Keyãæ¯ä¸ªä¸æ¸¸å»ºè®®çæç¬ç«å¯é¥ï¼ä¾¿äºåç¬è½®æ¢ä¸åç¨ã? width-class="w-80" />
                      </div>
                      <div class="relative">
                        <Input
                          v-model="client.apiKey"
                          :type="client.showApiKey ? 'text' : 'password'"
                          placeholder="çç©ºè¡¨ç¤ºä¸ä¿®æ?
                          class="h-11 pr-10 bg-white border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all font-mono text-sm"
                          :disabled="upstreamLoading"
                        />
                        <button
                          type="button"
                          @click="toggleShowUpstreamInboundClientApiKey(index)"
                          class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                        >
                          <EyeOff v-if="client.showApiKey" class="h-4 w-4" />
                          <Eye v-else class="h-4 w-4" />
                        </button>
                      </div>
                      <p class="text-xs text-gray-400">
                        <template v-if="client.apiKeyStored">å·²å
¥åºï¼çç©ºè¡¨ç¤ºä¸ä¿®æ¹ã?/template>
                        <template v-else-if="client.apiKeySet">å½åå¼å¯ç¨ä½æªå
¥åºï¼ä¿å­æ¶ä¼è¿ç§»æè¦çã?/template>
                        <template v-else>æªè®¾ç½®ã?/template>
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              <div class="rounded-2xl border border-gray-200 bg-gray-50/70 p-4 text-sm text-gray-600">
                <div class="flex items-center gap-2">
                  <p class="font-medium text-gray-900">åºå®å
¥ç«è·¯å¾</p>
                  <InfoTooltip content="è¿ä¸æ¡è·¯å¾ç±å¹³å°ç»ä¸ç»´æ¤ï¼å¤é¨å¯¹æ¥æ¹åªéè¦ææ åè·¯å¾æ¥å
¥å³å¯ï¼ä¸æ¸¸æ å°ç ä¹ç´æ¥èµ°è¿éã? width-class="w-72" />
                </div>
                <div class="mt-3 grid gap-2 md:grid-cols-3">
                  <code class="rounded-lg bg-white px-3 py-2 text-xs text-gray-700 shadow-sm">GET /api/upstream/health</code>
                  <code class="rounded-lg bg-white px-3 py-2 text-xs text-gray-700 shadow-sm">POST /api/upstream/cards/check</code>
                  <code class="rounded-lg bg-white px-3 py-2 text-xs text-gray-700 shadow-sm">POST /api/upstream/cards/redeem</code>
                </div>
              </div>
            </TabsContent>
          </Tabs>

          <div v-if="upstreamError" class="rounded-xl bg-red-50 p-4 text-red-600 border border-red-100 text-sm font-medium">
            {{ upstreamError }}
          </div>

          <div v-if="upstreamSuccess" class="rounded-xl bg-green-50 p-4 text-green-600 border border-green-100 text-sm font-medium">
            {{ upstreamSuccess }}
          </div>

          <div class="flex flex-col sm:flex-row gap-3">
            <Button
              type="button"
              variant="outline"
              class="w-full sm:w-auto h-11 rounded-xl"
              :disabled="upstreamLoading"
              @click="loadUpstreamSettings"
            >
              å·æ°
            </Button>
            <Button
              type="button"
              class="w-full sm:flex-1 h-11 rounded-xl bg-black hover:bg-gray-800 text-white shadow-lg shadow-black/5"
              :disabled="upstreamLoading"
              @click="saveUpstreamSettings"
            >
              {{ upstreamLoading ? 'ä¿å­ä¸?..' : 'ä¿å­ä¸ä¸æ¸¸æ¥å£é
ç½? }}
            </Button>
          </div>
        </CardContent>
      </Card>
      </template>

      <template v-if="settingsSubTab === 'billing'">
      <Card v-if="isSuperAdmin" class="bg-white rounded-[32px] border border-gray-100 shadow-sm overflow-hidden flex flex-col lg:col-span-2">
        <CardHeader class="border-b border-gray-50 bg-gray-50/30 px-6 py-5 sm:px-8 sm:py-6">
          <CardTitle class="text-xl font-bold text-gray-900">ZPAY æ¯ä»é
ç½®</CardTitle>
          <CardDescription class="text-gray-500">ç¨äºè´­ä¹°ä¸åä¸åè°éªç­¾ï¼ä¿å­åå®æ¶çæï¼ã</CardDescription>
        </CardHeader>
        <CardContent class="p-6 sm:p-8 space-y-6 flex-1">
          <div class="grid gap-4 lg:grid-cols-3">
            <div class="space-y-2 lg:col-span-1">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Base URL</Label>
              <Input
                v-model="zpayBaseUrl"
                type="text"
                placeholder="https://zpayz.cn"
                class="h-11 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all font-mono text-sm"
                :disabled="zpayLoading"
              />
              <p class="text-xs text-gray-400">ç¤ºä¾ï¼https://zpayz.cnï¼æ éä»?/ ç»å°¾ï¼</p>
            </div>
            <div class="space-y-2 lg:col-span-1">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">PID</Label>
              <Input
                v-model="zpayPid"
                type="text"
                placeholder="ZPAY PID"
                class="h-11 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all font-mono text-sm"
                :disabled="zpayLoading"
              />
              <p class="text-xs text-gray-400">çç©ºè¡¨ç¤ºä¸å¯ç¨æ¯ä»ã</p>
            </div>
            <div class="space-y-2 lg:col-span-1">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">KEY</Label>
              <div class="relative">
                <Input
                  v-model="zpayKey"
                  :type="showZpayKey ? 'text' : 'password'"
                  placeholder="çç©ºè¡¨ç¤ºä¸ä¿®æ?
                  class="h-11 pr-10 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all font-mono text-sm"
                  :disabled="zpayLoading"
                />
                <button
                  type="button"
                  @click="toggleShowZpayKey"
                  class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                >
                  <EyeOff v-if="showZpayKey" class="h-4 w-4" />
                  <Eye v-else class="h-4 w-4" />
                </button>
              </div>
              <p class="text-xs text-gray-400">
                <template v-if="zpayKeyStored">KEY å·²å
¥åºï¼çç©ºè¡¨ç¤ºä¸ä¿®æ¹ã?/template>
                <template v-else-if="zpayKeySet">KEY æªå
¥åºï¼ä¿å­æ¶å¯ä»?.env èªå¨è¿ç§»æå¨æ­¤éæ°å¡«åã?/template>
                <template v-else>æªè®¾ç½?KEYã?/template>
              </p>
            </div>
          </div>

          <div v-if="zpayError" class="rounded-xl bg-red-50 p-4 text-red-600 border border-red-100 text-sm font-medium">
            {{ zpayError }}
          </div>

          <div v-if="zpaySuccess" class="rounded-xl bg-green-50 p-4 text-green-600 border border-green-100 text-sm font-medium">
            {{ zpaySuccess }}
          </div>

          <div class="flex flex-col sm:flex-row gap-3">
            <Button
              type="button"
              variant="outline"
              class="w-full sm:w-auto h-11 rounded-xl"
              :disabled="zpayLoading"
              @click="loadZpaySettings"
            >
              å·æ°
            </Button>
            <Button
              type="button"
              class="w-full sm:flex-1 h-11 rounded-xl bg-black hover:bg-gray-800 text-white shadow-lg shadow-black/5"
              :disabled="zpayLoading"
              @click="saveZpaySettings"
            >
              {{ zpayLoading ? 'ä¿å­ä¸?..' : 'ä¿å­ ZPAY é
ç½®' }}
            </Button>
          </div>
        </CardContent>
      </Card>
      </template>

      <template v-if="settingsSubTab === 'integrations'">
      <Card v-if="isSuperAdmin" class="bg-white rounded-[32px] border border-gray-100 shadow-sm overflow-hidden flex flex-col lg:col-span-2">
        <CardHeader class="border-b border-gray-50 bg-gray-50/30 px-6 py-5 sm:px-8 sm:py-6">
          <CardTitle class="text-xl font-bold text-gray-900">Cloudflare Turnstile é
ç½®</CardTitle>
          <CardDescription class="text-gray-500">ç¨äºåè½¦å®¤å å
¥éåçäººæºéªè¯ï¼ä¿å­åå®æ¶çæï¼ã</CardDescription>
        </CardHeader>
        <CardContent class="p-6 sm:p-8 space-y-6 flex-1">
          <div class="text-xs text-gray-500">
            å½åç¶æï¼<span class="font-semibold">{{ turnstileEnabled ? 'å·²å¯ç? : 'æªå¯ç? }}</span>
            <span class="text-gray-400">ï¼éåæ¶é
ç½® Site Key + Secret Keyï¼?/span>
          </div>

          <div class="grid gap-4 lg:grid-cols-2">
            <div class="space-y-2">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Site Key</Label>
              <Input
                v-model="turnstileSiteKey"
                type="text"
                placeholder="0x..."
                class="h-11 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all font-mono text-sm"
                :disabled="turnstileLoading"
              />
              <p class="text-xs text-gray-400">çç©ºè¡¨ç¤ºç¦ç¨äººæºéªè¯ã</p>
            </div>

            <div class="space-y-2">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Secret Key</Label>
              <div class="relative">
                <Input
                  v-model="turnstileSecretKey"
                  :type="showTurnstileSecretKey ? 'text' : 'password'"
                  placeholder="çç©ºè¡¨ç¤ºä¸ä¿®æ?
                  class="h-11 pr-10 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all font-mono text-sm"
                  :disabled="turnstileLoading"
                />
                <button
                  type="button"
                  @click="toggleShowTurnstileSecretKey"
                  class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                >
                  <EyeOff v-if="showTurnstileSecretKey" class="h-4 w-4" />
                  <Eye v-else class="h-4 w-4" />
                </button>
              </div>
              <p class="text-xs text-gray-400">
                <template v-if="turnstileSecretStored">Secret Key å·²å
¥åºï¼çç©ºè¡¨ç¤ºä¸ä¿®æ¹ã?/template>
                <template v-else-if="turnstileSecretSet">Secret Key æªå
¥åºï¼ä¿å­æ¶å¯ä»?.env èªå¨è¿ç§»æå¨æ­¤éæ°å¡«åã?/template>
                <template v-else>æªè®¾ç½?Secret Keyã?/template>
              </p>
            </div>
          </div>

          <div v-if="turnstileError" class="rounded-xl bg-red-50 p-4 text-red-600 border border-red-100 text-sm font-medium">
            {{ turnstileError }}
          </div>

          <div v-if="turnstileSuccess" class="rounded-xl bg-green-50 p-4 text-green-600 border border-green-100 text-sm font-medium">
            {{ turnstileSuccess }}
          </div>

          <div class="flex flex-col sm:flex-row gap-3">
            <Button
              type="button"
              variant="outline"
              class="w-full sm:w-auto h-11 rounded-xl"
              :disabled="turnstileLoading"
              @click="loadTurnstileSettings"
            >
              å·æ°
            </Button>
            <Button
              type="button"
              class="w-full sm:flex-1 h-11 rounded-xl bg-black hover:bg-gray-800 text-white shadow-lg shadow-black/5"
              :disabled="turnstileLoading"
              @click="saveTurnstileSettings"
            >
              {{ turnstileLoading ? 'ä¿å­ä¸?..' : 'ä¿å­ Turnstile é
ç½®' }}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card v-if="isSuperAdmin" class="bg-white rounded-[32px] border border-gray-100 shadow-sm overflow-hidden flex flex-col lg:col-span-2">
        <CardHeader class="border-b border-gray-50 bg-gray-50/30 px-6 py-5 sm:px-8 sm:py-6">
          <CardTitle class="text-xl font-bold text-gray-900">Telegram Bot é
ç½®</CardTitle>
          <CardDescription class="text-gray-500">ç¨äº Telegram å
æ¢æºå¨äººä¸ç³»ç»éç¥ã</CardDescription>
        </CardHeader>
        <CardContent class="p-6 sm:p-8 space-y-6 flex-1">
          <div class="grid gap-4 lg:grid-cols-2">
            <div class="space-y-2">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Bot Token</Label>
              <div class="relative">
                <Input
                  v-model="telegramBotToken"
                  :type="showTelegramBotToken ? 'text' : 'password'"
                  placeholder="çç©ºè¡¨ç¤ºä¸ä¿®æ?
                  class="h-11 pr-10 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all font-mono text-sm"
                  :disabled="telegramLoading"
                />
                <button
                  type="button"
                  @click="toggleShowTelegramBotToken"
                  class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                >
                  <EyeOff v-if="showTelegramBotToken" class="h-4 w-4" />
                  <Eye v-else class="h-4 w-4" />
                </button>
              </div>
              <p class="text-xs text-gray-400">
                <template v-if="telegramTokenStored">Token å·²å
¥åºï¼çç©ºè¡¨ç¤ºä¸ä¿®æ¹ã?/template>
                <template v-else-if="telegramTokenSet">Token æªå
¥åºï¼ä¿å­æ¶å¯ä»?.env èªå¨è¿ç§»æå¨æ­¤éæ°å¡«åã?/template>
                <template v-else>æªè®¾ç½?Tokenã?/template>
              </p>
            </div>

            <div class="space-y-2">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">å
è®¸çç¨æ?ID (å¯é?</Label>
              <Input
                v-model="telegramAllowedUserIds"
                type="text"
                placeholder="123456,789012"
                class="h-11 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all font-mono text-sm"
                :disabled="telegramLoading"
              />
              <p class="text-xs text-gray-400">çç©ºè¡¨ç¤ºå¯¹ææç¨æ·å¼æ¾ï¼å¡«ååä»
å
è®¸è¿äº Telegram User IDã</p>
            </div>
          </div>

          <div class="grid gap-4 lg:grid-cols-3">
            <div class="space-y-2">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">éç¥å¼å
</Label>
              <Select v-model="telegramNotifyEnabled" :disabled="telegramLoading">
                <SelectTrigger class="h-11 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all">
                  <SelectValue placeholder="éæ©" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="true">å¯ç¨éç¥</SelectItem>
                  <SelectItem value="false">ç¦ç¨éç¥</SelectItem>
                </SelectContent>
              </Select>
              <p class="text-xs text-gray-400">
                <template v-if="telegramNotifyEnabledStored">å·²å
¥åºã?/template>
                <template v-else>æªå
¥åºï¼å½åå¼å¯è½æ¥è?.envï¼ã?/template>
              </p>
            </div>

            <div class="space-y-2">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">éç¥ chat_id (å¯é?</Label>
              <Input
                v-model="telegramNotifyChatIds"
                type="text"
                placeholder="-1001234567890,@channelname"
                class="h-11 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all font-mono text-sm"
                :disabled="telegramLoading"
              />
              <p class="text-xs text-gray-400">
                <template v-if="telegramNotifyChatIdsStored">å·²å
¥åºã?/template>
                <template v-else>æªå
¥åºï¼å½åå¼å¯è½æ¥è?.envï¼ã?/template>
                çç©ºåé»è®¤åéç»ãå
è®¸çç¨æ· IDãï¼æ¯æç¨æ·ID/ç¾¤IDï¼?100...ï¼?é¢éï¼@xxxï¼ï¼éå·åéã?
              </p>
            </div>

            <div class="space-y-2">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">éç¥è¶
æ¶ï¼æ¯«ç§ï¼</Label>
              <Input
                v-model="telegramNotifyTimeoutMs"
                type="text"
                placeholder="8000"
                class="h-11 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all font-mono text-sm"
                :disabled="telegramLoading"
              />
              <p class="text-xs text-gray-400">
                <template v-if="telegramNotifyTimeoutMsStored">å·²å
¥åºã?/template>
                <template v-else>æªå
¥åºï¼å½åå¼å¯è½æ¥è?.envï¼ã?/template>
              </p>
            </div>
          </div>

          <div v-if="telegramError" class="rounded-xl bg-red-50 p-4 text-red-600 border border-red-100 text-sm font-medium">
            {{ telegramError }}
          </div>

          <div v-if="telegramSuccess" class="rounded-xl bg-green-50 p-4 text-green-600 border border-green-100 text-sm font-medium">
            {{ telegramSuccess }}
          </div>

          <div class="flex flex-col sm:flex-row gap-3">
            <Button
              type="button"
              variant="outline"
              class="w-full sm:w-auto h-11 rounded-xl"
              :disabled="telegramLoading"
              @click="loadTelegramSettings"
            >
              å·æ°
            </Button>
            <Button
              type="button"
              class="w-full sm:flex-1 h-11 rounded-xl bg-black hover:bg-gray-800 text-white shadow-lg shadow-black/5"
              :disabled="telegramLoading"
              @click="saveTelegramSettings"
            >
              {{ telegramLoading ? 'ä¿å­ä¸?..' : 'ä¿å­ Telegram é
ç½®' }}
            </Button>
          </div>
        </CardContent>
      </Card>

      </template>

      <template v-if="settingsSubTab === 'billing'">
      <!-- ç§¯åæç°è®¾ç½® -->
      <Card v-if="isSuperAdmin" class="bg-white rounded-[32px] border border-gray-100 shadow-sm overflow-hidden flex flex-col lg:col-span-2">
	          <CardHeader class="border-b border-gray-50 bg-gray-50/30 px-6 py-5 sm:px-8 sm:py-6">
	            <CardTitle class="text-xl font-bold text-gray-900">ç§¯åæç°è®¾ç½®</CardTitle>
	            <CardDescription class="text-gray-500">é
ç½®è¿ç°æ¯ä¾ä¸æç°é¨æ§ï¼ä¿å­åå®æ¶çæï¼ã</CardDescription>
	          </CardHeader>
	          <CardContent class="p-6 sm:p-8 space-y-6 flex-1">
	            <div class="grid gap-4 lg:grid-cols-3">
	              <div class="space-y-2">
	                <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">è¿ç°æ¯ä¾ï¼ç§¯å</Label>
                <Input
                  v-model="pointsWithdrawRatePoints"
                  type="text"
                  placeholder="1"
                  class="h-11 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all"
                  :disabled="pointsWithdrawLoading"
                />
              </div>
              <div class="space-y-2">
                <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">è¿ç°æ¯ä¾ï¼éé¢ï¼å
ï¼</Label>
                <Input
                  v-model="pointsWithdrawRateCashYuan"
                  type="text"
                  placeholder="1.00"
                  class="h-11 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all"
                  :disabled="pointsWithdrawLoading"
                />
              </div>
              <div class="space-y-2">
                <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">æä½æç°éé¢ï¼å
ï¼</Label>
                <Input
                  v-model="pointsWithdrawMinCashYuan"
                  type="text"
                  placeholder="10.00"
                  class="h-11 bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-500 transition-all"
                  :disabled="pointsWithdrawLoading"
                />
              </div>
            </div>

            <div class="text-xs text-gray-500">
              å½åè§åï¼{{ pointsWithdrawRatePoints }} ç§¯å = {{ pointsWithdrawRateCashYuan }} å
ï¼æä½æç°çº¦ {{ pointsWithdrawMinPoints ?? '-' }} ç§¯åï¼æ­¥è¿?{{ pointsWithdrawStepPoints ?? '-' }} ç§¯å
            </div>

            <div v-if="pointsWithdrawError" class="rounded-xl bg-red-50 p-4 text-red-600 border border-red-100 text-sm font-medium">
              {{ pointsWithdrawError }}
            </div>

            <div v-if="pointsWithdrawSuccess" class="rounded-xl bg-green-50 p-4 text-green-600 border border-green-100 text-sm font-medium">
              {{ pointsWithdrawSuccess }}
            </div>

	            <div class="flex flex-col sm:flex-row gap-3">
	              <Button
	                type="button"
	                variant="outline"
	                class="w-full sm:w-auto h-11 rounded-xl"
	                :disabled="pointsWithdrawLoading"
	                @click="loadPointsWithdrawSettings"
	              >
	                å·æ°
	              </Button>
	              <Button
	                type="button"
	                class="w-full sm:flex-1 h-11 rounded-xl bg-black hover:bg-gray-800 text-white shadow-lg shadow-black/5"
	                :disabled="pointsWithdrawLoading"
	                @click="savePointsWithdrawSettings"
	              >
	                {{ pointsWithdrawLoading ? 'ä¿å­ä¸?..' : 'ä¿å­è®¾ç½®' }}
              </Button>
            </div>
          </CardContent>
      </Card>
      </template>

      <Dialog v-model:open="channelDialogOpen">
        <DialogContent class="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle class="text-xl font-bold text-gray-900">{{ channelDialogMode === 'create' ? 'æ°å¢æ¸ é' : 'ç¼è¾æ¸ é' }}</DialogTitle>
            <DialogDescription class="text-gray-500">æ¸ é key ä»
æ¯æå°åå­æ¯?æ°å­/è¿å­ç¬¦ã?/DialogDescription>
          </DialogHeader>

          <div class="space-y-4 py-4">
            <div class="space-y-2">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">æ¸ é Key</Label>
              <Input v-model="channelFormKey" :disabled="channelDialogMode === 'edit'" placeholder="douyin" class="h-11 bg-gray-50 border-gray-200 rounded-xl font-mono text-sm" />
            </div>
            <div class="space-y-2">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">æ¸ éåç§°</Label>
              <Input v-model="channelFormName" placeholder="æé³æ¸ é" class="h-11 bg-gray-50 border-gray-200 rounded-xl text-sm" />
            </div>
            <div class="grid gap-3 sm:grid-cols-2">
              <div class="space-y-2">
                <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">å
æ¢æ¨¡å¼</Label>
                <Select v-model="channelFormRedeemMode">
                  <SelectTrigger class="h-11 bg-gray-50 border-gray-200 rounded-xl">
                    <SelectValue placeholder="è¯·éæ©å
æ¢æ¨¡å¼" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem v-for="option in channelRedeemModeOptions" :key="option.value" :value="option.value">
                      {{ option.label }}
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div class="space-y-2">
                <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">å±¥çº¦ Provider</Label>
                <Select v-model="channelFormProviderType" :disabled="channelFormProviderOptions.length <= 1">
                  <SelectTrigger class="h-11 bg-gray-50 border-gray-200 rounded-xl">
                    <SelectValue placeholder="è¯·éæ© Provider" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem v-for="option in channelFormProviderOptions" :key="option.value" :value="option.value">
                      {{ option.label }}
                    </SelectItem>
                  </SelectContent>
                </Select>
                <p class="text-xs text-gray-400">
                  <template v-if="channelFormRedeemMode === 'external-card'">å¤é¨å¡å¯æ¸ éå¯éæ©èªå®ä¹æ¥å£æå¹³å°éç¨æ¥å£ã?/template>
                  <template v-else>é?external-card æ¸ éåºå®ä½¿ç¨æ¬å°å±¥çº¦ã?/template>
                </p>
              </div>
            </div>
            <div class="flex items-center justify-between p-4 bg-gray-50 rounded-2xl border border-gray-100">
              <div class="space-y-1">
                <p class="font-medium text-gray-900">å
è®¸åééç¨ç </p>
                <p class="text-xs text-gray-500">å¼å¯åå¯å¨è¯¥æ¸ éå
¥å£ä½¿ç¨éç¨æ¸ éå
æ¢ç ã</p>
              </div>
              <input type="checkbox" v-model="channelFormAllowFallback" class="w-6 h-6 rounded-md border-gray-300 text-blue-600 focus:ring-blue-500" />
            </div>
            <div class="flex items-center justify-between p-4 bg-gray-50 rounded-2xl border border-gray-100">
              <div class="space-y-1">
                <p class="font-medium text-gray-900">å
è®¸åä¸ä¸æ¸¸å®ç </p>
                <p class="text-xs text-gray-500">å¼å¯åï¼è¯¥æ¸ éä¸å¯å®å
æ¢ç ä¼è¿å
?/downstream å
±äº«åºå­ã</p>
              </div>
              <input type="checkbox" v-model="channelFormAllowDownstreamSale" class="w-6 h-6 rounded-md border-gray-300 text-blue-600 focus:ring-blue-500" />
            </div>
            <div class="flex items-center justify-between p-4 bg-gray-50 rounded-2xl border border-gray-100">
              <div class="space-y-1">
                <p class="font-medium text-gray-900">å¯ç¨</p>
              </div>
              <input type="checkbox" v-model="channelFormIsActive" class="w-6 h-6 rounded-md border-gray-300 text-blue-600 focus:ring-blue-500" />
            </div>
            <div class="space-y-2">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">æåºï¼sortOrderï¼</Label>
              <Input v-model="channelFormSortOrder" type="number" class="h-11 bg-gray-50 border-gray-200 rounded-xl font-mono text-sm" />
            </div>

            <div class="flex flex-col sm:flex-row gap-3 pt-2">
              <Button type="button" variant="outline" class="w-full sm:w-auto h-11 px-4 border-gray-200 rounded-xl" @click="channelDialogOpen = false">
                åæ¶
              </Button>
              <Button type="button" class="w-full h-11 rounded-xl bg-black hover:bg-gray-800 text-white shadow-lg shadow-black/5" @click="submitChannelDialog">
                ä¿å­
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog v-model:open="purchaseProductDialogOpen">
        <DialogContent class="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle class="text-xl font-bold text-gray-900">{{ purchaseProductDialogMode === 'create' ? 'æ°å¢åå' : 'ç¼è¾åå' }}</DialogTitle>
            <DialogDescription class="text-gray-500">codeChannels æä¼å
çº§ç¨è±æéå·åéï¼ä¾å¦ï¼paypal,common</DialogDescription>
          </DialogHeader>

          <div class="space-y-4 py-4">
            <div class="space-y-2">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">åå Key</Label>
              <Input v-model="purchaseProductFormKey" :disabled="purchaseProductDialogMode === 'edit'" placeholder="warranty_90" class="h-11 bg-gray-50 border-gray-200 rounded-xl font-mono text-sm" />
            </div>
            <div class="space-y-2">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">åç§°</Label>
              <Input v-model="purchaseProductFormName" placeholder="è´¨ä¿ 90 å¤? class="h-11 bg-gray-50 border-gray-200 rounded-xl text-sm" />
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div class="space-y-2">
                <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">ä»·æ ¼ï¼amountï¼</Label>
                <Input v-model="purchaseProductFormAmount" placeholder="15.00" class="h-11 bg-gray-50 border-gray-200 rounded-xl font-mono text-sm" />
              </div>
              <div class="space-y-2">
                <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">æå¡æï¼å¤©ï¼</Label>
                <Input v-model="purchaseProductFormServiceDays" type="number" class="h-11 bg-gray-50 border-gray-200 rounded-xl font-mono text-sm" />
              </div>
            </div>
            <div class="space-y-2">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">è®¢åç±»åï¼orderTypeï¼</Label>
              <Select v-model="purchaseProductFormOrderType">
                <SelectTrigger class="h-11 bg-gray-50 border-gray-200 rounded-xl">
                  <SelectValue placeholder="è¯·éæ©" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="warranty">warranty</SelectItem>
                  <SelectItem value="no_warranty">no_warranty</SelectItem>
                  <SelectItem value="anti_ban">anti_ban</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div class="space-y-2">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">æ¸ éç­ç¥ï¼codeChannelsï¼</Label>
              <Input v-model="purchaseProductFormCodeChannels" placeholder="paypal,common" class="h-11 bg-gray-50 border-gray-200 rounded-xl font-mono text-sm" />
              <p class="text-xs text-gray-400">å¯ç¨æ¸ éï¼{{ channels.map(c => c.key).join(', ') || 'ï¼ææ ï¼' }}</p>
            </div>
            <div class="flex items-center justify-between p-4 bg-gray-50 rounded-2xl border border-gray-100">
              <div class="space-y-1">
                <p class="font-medium text-gray-900">ä¸æ¶</p>
              </div>
              <input type="checkbox" v-model="purchaseProductFormIsActive" class="w-6 h-6 rounded-md border-gray-300 text-blue-600 focus:ring-blue-500" />
            </div>
            <div class="space-y-2">
              <Label class="text-xs font-semibold text-gray-500 uppercase tracking-wider">æåºï¼sortOrderï¼</Label>
              <Input v-model="purchaseProductFormSortOrder" type="number" class="h-11 bg-gray-50 border-gray-200 rounded-xl font-mono text-sm" />
            </div>

            <div class="flex flex-col sm:flex-row gap-3 pt-2">
              <Button type="button" variant="outline" class="w-full sm:w-auto h-11 px-4 border-gray-200 rounded-xl" @click="purchaseProductDialogOpen = false">
                åæ¶
              </Button>
              <Button type="button" class="w-full h-11 rounded-xl bg-black hover:bg-gray-800 text-white shadow-lg shadow-black/5" @click="submitPurchaseProductDialog">
                ä¿å­
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
          </div>
        </div>
      </div>
    </TabsContent>

    <TabsContent v-if="isSuperAdmin" value="announcements" class="mt-0">
      <AnnouncementAdminPanel />
    </TabsContent>
  </Tabs>
</template>


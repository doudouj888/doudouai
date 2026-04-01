<template>
  <RedeemShell max-width="max-w-[420px]">
    <section class="redeem-page">
      <div class="redeem-panel">
        <header class="panel-header">
          <p class="panel-kicker">通用兑换</p>
          <h1>卡密兑换</h1>
          <p class="panel-copy">填写卡密和邮箱后提交即可。</p>
        </header>

        <form class="redeem-form" @submit.prevent="handleRedeem()">
          <div class="field-group">
            <label>邮箱</label>
            <AppleInput
              v-model.trim="formData.email"
              type="email"
              placeholder="name@example.com"
              variant="filled"
              :disabled="isLoading"
              :error="formData.email && !isValidEmail ? '请输入有效的邮箱地址' : ''"
              autocomplete="email"
              auto-focus
            />
          </div>

          <div class="field-group">
            <label>卡密</label>
            <AppleInput
              v-model="formData.code"
              type="text"
              placeholder="XXXX-XXXX-XXXX"
              variant="filled"
              :disabled="isLoading"
              :error="formData.code && !isValidCode ? '卡密格式不正确' : ''"
              autocomplete="off"
              @input="handleCodeInput"
            />
          </div>

          <div v-if="successInfo" class="feedback-card success-card">
            <p class="feedback-title">兑换成功</p>
            <p class="feedback-text">
              {{ successInfo.message || '兑换已提交成功，请留意邮箱通知。' }}
            </p>
          </div>

          <div v-if="errorMessage" class="feedback-card error-card">
            <p class="feedback-title">提交失败</p>
            <p class="feedback-text">{{ errorMessage }}</p>
          </div>

          <AppleButton
            type="submit"
            variant="primary"
            size="lg"
            class-name="redeem-submit"
            :loading="isLoading"
            :disabled="isLoading"
          >
            {{ isLoading ? '兑换中...' : '立即兑换' }}
          </AppleButton>
        </form>

        <div class="tips-block">
          <p class="tips-title">提示</p>
          <ul class="tips-list">
            <li>请确认邮箱填写正确，兑换结果会发送到该邮箱。</li>
            <li>若提示卡密无效或已使用，请联系管理员处理。</li>
            <li>填完卡密后若未收到邀请链接，可重新登录账号查看空间是否已添加。</li>
          </ul>
        </div>
      </div>
    </section>
  </RedeemShell>
</template>

<script setup lang="ts">
import AppleButton from '@/components/ui/apple/Button.vue'
import AppleInput from '@/components/ui/apple/Input.vue'
import RedeemShell from '@/components/RedeemShell.vue'
import { useRedeemForm } from '@/composables/useRedeemForm'

const {
  formData,
  isLoading,
  errorMessage,
  successInfo,
  isValidEmail,
  isValidCode,
  handleCodeInput,
  handleRedeem,
} = useRedeemForm()
</script>

<style scoped>
.redeem-page {
  min-height: auto;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 1.75rem 0 1.5rem;
}

.redeem-panel {
  width: 100%;
  max-width: 420px;
  border-radius: 28px;
  padding: 32px 28px 24px;
  margin-top: 1.5rem;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(255, 255, 255, 0.72);
  box-shadow: 0 18px 50px rgba(15, 23, 42, 0.10);
  backdrop-filter: blur(22px);
}

.panel-header {
  text-align: center;
  margin-bottom: 22px;
  color: #0f172a;
}

.panel-kicker {
  margin: 0 0 8px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #64748b;
}

.panel-header h1 {
  margin: 0;
  font-size: 28px;
  line-height: 1.15;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.panel-copy {
  margin: 10px 0 0;
  font-size: 13px;
  line-height: 1.6;
  color: #64748b;
}

.redeem-form {
  display: grid;
  gap: 14px;
}

.field-group label {
  display: block;
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
}

.feedback-card {
  border-radius: 16px;
  padding: 13px 14px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: rgba(255, 255, 255, 0.7);
  color: #0f172a;
}

.feedback-title {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
}

.feedback-text {
  margin: 6px 0 0;
  font-size: 14px;
  line-height: 1.6;
}

.success-card {
  border-color: rgba(34, 197, 94, 0.4);
  background: rgba(34, 197, 94, 0.08);
  color: #166534;
}

.error-card {
  border-color: rgba(239, 68, 68, 0.4);
  background: rgba(239, 68, 68, 0.08);
  color: #b91c1c;
}

:deep(.redeem-submit) {
  width: 100%;
  height: 52px;
  border-radius: 16px;
  font-size: 16px;
  font-weight: 600;
  box-shadow: 0 10px 24px rgba(0, 122, 255, 0.18);
}

.tips-block {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid rgba(148, 163, 184, 0.14);
}

.tips-title {
  margin: 0 0 10px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #94a3b8;
}

.tips-list {
  list-style: none;
  margin: 0;
  padding: 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.65;
}

.tips-list li {
  position: relative;
  padding-left: 14px;
}

.tips-list li::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0.55rem;
  width: 5px;
  height: 5px;
  border-radius: 999px;
  background: #94a3b8;
}

.tips-list li + li {
  margin-top: 6px;
}

@media (max-width: 640px) {
  .redeem-page {
    min-height: auto;
  }

  .redeem-panel {
    padding: 26px 20px 22px;
    margin-top: 2rem;
    border-radius: 24px;
  }

  .panel-header h1 {
    font-size: 26px;
  }
}

@media (max-width: 480px) {
  .redeem-page {
    align-items: flex-start;
    padding: 0.5rem 0 1.5rem;
  }

  .redeem-panel {
    padding: 22px 18px 20px;
    border-radius: 20px;
    margin-top: 2.5rem;
  }

  .redeem-form {
    gap: 12px;
  }

  :deep(.redeem-submit) {
    height: 48px;
  }
}
</style>

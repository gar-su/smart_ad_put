<template>
  <div class="config-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>信号配置</span>
          <div>
            <el-button @click="load">刷新</el-button>
            <el-button type="primary" :loading="saving" @click="save">保存配置</el-button>
          </div>
        </div>
      </template>

      <el-form label-width="130px" style="max-width: 720px">
        <el-form-item label="冷却时长">
          <el-input-number v-model="form.cooldown_hours" :min="1" :step="1" />
          <span class="hint">小时 · 同一目标同类型信号在冷却期内不重复产出（PRD §5.5.2）</span>
        </el-form-item>

        <el-form-item label="值得跟投的阶段">
          <div style="width: 100%">
            <el-checkbox-group v-model="form.follow_up_stages">
              <div v-for="group in stageGroups" :key="group.dimension" class="stage-group">
                <div class="group-label">{{ group.label }}</div>
                <el-checkbox
                  v-for="s in group.stages"
                  :key="s.value"
                  :value="s.value"
                >{{ s.label }}</el-checkbox>
              </div>
            </el-checkbox-group>
            <div class="hint">命中值得跟投阶段 → 输出 FOLLOW_UP 信号，交由下游 machine-delivery 新建放量任务</div>
          </div>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

// 后端不可达时兜底展示（与 PRD §5.5.2 默认一致）
const DEFAULT_RULES = {
  follow_up_stages: [
    'product_entry',
    'product_growth',
    'product_sustained',
    'campaign_growth',
    'campaign_sustained',
  ],
  cooldown_hours: 24,
}

const DEFAULT_STAGES: { value: string; label: string }[] = [
  { value: 'campaign_observing', label: '待观察' },
  { value: 'campaign_cold_dead', label: '冷死亡' },
  { value: 'campaign_cold_start', label: '冷启动' },
  { value: 'campaign_verify', label: '验证期' },
  { value: 'campaign_growth', label: '成长期' },
  { value: 'campaign_sustained', label: '持续盈利' },
  { value: 'campaign_decline', label: '衰退期' },
  { value: 'campaign_shutdown', label: '关停期' },
  { value: 'product_observing', label: '待观察' },
  { value: 'product_entry', label: '入场期' },
  { value: 'product_sustained', label: '稳定期' },
  { value: 'product_growth', label: '成长期' },
  { value: 'product_decline', label: '衰退期' },
  { value: 'product_exit', label: '退出期' },
]

const form = reactive({ ...DEFAULT_RULES })
const availableStages = ref<{ value: string; label: string }[]>([])
const saving = ref(false)

const stageGroups = computed(() => {
  const groups: { dimension: string; label: string; stages: { value: string; label: string }[] }[] = [
    { dimension: 'product', label: '商品（短剧）', stages: [] },
    { dimension: 'campaign', label: '广告单元（Campaign）', stages: [] },
  ]
  for (const s of availableStages.value) {
    const g = s.value.startsWith('product_') ? groups[0] : groups[1]
    g.stages.push(s)
  }
  return groups.filter(g => g.stages.length > 0)
})

async function load() {
  try {
    const res = await fetch('/api/signals/config')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    form.follow_up_stages = data.rules.follow_up_stages ?? []
    form.cooldown_hours = data.rules.cooldown_hours ?? DEFAULT_RULES.cooldown_hours
    availableStages.value = data.available_stages ?? []
  } catch {
    availableStages.value = [...DEFAULT_STAGES]
    ElMessage.warning('后端未连接，展示示例配置')
  }
}

async function save() {
  saving.value = true
  try {
    const res = await fetch('/api/signals/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        follow_up_stages: [...form.follow_up_stages],
        cooldown_hours: form.cooldown_hours,
      }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    ElMessage.success('配置已保存，下次 pipeline 运行生效')
  } catch {
    ElMessage.error('保存失败，请检查后端服务')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.hint {
  margin-left: 10px;
  color: #909399;
  font-size: 13px;
}

.stage-group {
  margin-bottom: 14px;
}

.group-label {
  font-size: 13px;
  font-weight: 600;
  color: #606266;
  margin-bottom: 8px;
}

.stage-group :deep(.el-checkbox) {
  width: 150px;
  margin-right: 8px;
}
</style>
<template>
  <div class="config-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>信号配置</span>
          <span class="mock-tag">前端示例数据</span>
        </div>
      </template>

      <el-table :data="rules" border stripe size="default">
        <el-table-column label="维度" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.group === 'product'" type="success" size="small">短剧</el-tag>
            <el-tag v-else-if="row.group === 'campaign'" type="primary" size="small">广告单元</el-tag>
            <el-tag v-else-if="row.group === 'material'" type="warning" size="small">素材</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="阶段" width="140">
          <template #default="{ row }">{{ row.label }}</template>
        </el-table-column>
        <el-table-column label="阶段标识" min-width="180">
          <template #default="{ row }">
            <span class="muted-key">{{ row.key }}</span>
          </template>
        </el-table-column>
        <el-table-column label="信号类型" width="140" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.signalType === 'FOLLOW_UP'" type="success" size="small">跟投</el-tag>
            <el-tag v-else-if="row.signalType === 'ELIMINATE'" type="danger" size="small">淘汰</el-tag>
            <el-tag v-else type="info" size="small">不产出</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="冷却时长（小时）" width="150" align="center">
          <template #default="{ row }">{{ row.cooldown }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>

      <p class="hint">选择「跟投」的阶段 → 输出 FOLLOW_UP 信号，交由下游 machine-delivery 新建放量任务；选择「淘汰」的阶段 → 输出 ELIMINATE 信号，下游停投并移除任务。同一阶段只能二选一；冷却时长按阶段独立配置，同一目标同类型信号在各自冷却期内不重复产出。素材阶段已纳入配置范围；本页为前端示例数据，保存仅作用于当前页面。</p>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="`编辑 ${editingKey}`" width="380px">
      <el-form label-width="96px">
        <el-form-item label="信号类型">
          <el-select v-model="form.signalType" style="width: 100%">
            <el-option label="跟投（FOLLOW_UP）" value="FOLLOW_UP" />
            <el-option label="淘汰（ELIMINATE）" value="ELIMINATE" />
            <el-option label="不产出" value="" />
          </el-select>
        </el-form-item>
        <el-form-item label="冷却时长">
          <el-input-number v-model="form.cooldown" :min="1" :step="1" :disabled="!form.signalType" />
          <span class="unit">小时</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmEdit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

// 前端 mock：不请求后端，页面数据源即此处示例配置（与 PRD §5.5.2 默认一致）
const MOCK_RULES = {
  follow_up_stages: [
    'product_entry',
    'product_growth',
    'product_sustained',
    'campaign_growth',
    'campaign_sustained',
    'material_entry',
    'material_sustained',
  ],
  eliminate_stages: ['product_exit', 'product_decline'],
  cooldown_hours: 24,
  cooldown_map: {
    product_entry: 12,
    campaign_growth: 8,
  },
}

const MOCK_STAGES: { value: string; label: string }[] = [
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
  { value: 'material_observing', label: '待观察' },
  { value: 'material_entry', label: '入场期' },
  { value: 'material_sustained', label: '稳定期' },
  { value: 'material_fatigue', label: '疲劳期' },
  { value: 'material_eliminated', label: '淘汰期' },
]

type SignalType = '' | 'FOLLOW_UP' | 'ELIMINATE'

interface StageRow {
  kind: 'stage'
  key: string
  label: string
  group: string
  signalType: SignalType
  cooldown: number
}

const defaultCooldown = ref(MOCK_RULES.cooldown_hours)
const rules = ref<StageRow[]>([])

function buildRows(
  followStages: string[],
  eliminateStages: string[],
  cooldownMap: Record<string, number>,
) {
  const follow = new Set(followStages)
  const eliminate = new Set(eliminateStages)
  rules.value = MOCK_STAGES.map((s) => ({
    kind: 'stage',
    key: s.value,
    label: s.label,
    group: s.value.startsWith('product_')
      ? 'product'
      : s.value.startsWith('material_')
        ? 'material'
        : 'campaign',
    signalType: follow.has(s.value) ? 'FOLLOW_UP' : eliminate.has(s.value) ? 'ELIMINATE' : '',
    cooldown: cooldownMap[s.value] ?? defaultCooldown.value,
  }))
}

buildRows(MOCK_RULES.follow_up_stages, MOCK_RULES.eliminate_stages, MOCK_RULES.cooldown_map)

const dialogVisible = ref(false)
const editingKey = ref('')
const form = ref<{ signalType: SignalType; cooldown: number }>({ signalType: '', cooldown: 1 })

function openEdit(row: StageRow) {
  editingKey.value = row.key
  form.value = { signalType: row.signalType, cooldown: row.cooldown }
  dialogVisible.value = true
}

function confirmEdit() {
  const row = rules.value.find((r) => r.key === editingKey.value)
  if (row) {
    row.signalType = form.value.signalType
    row.cooldown = form.value.cooldown
  }
  dialogVisible.value = false
  ElMessage.success('已保存（前端 mock，未落库）')
}
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.mock-tag {
  color: #909399;
  font-size: 12px;
}

.hint {
  margin-top: 14px;
  color: #909399;
  font-size: 13px;
}

.muted-key {
  color: #909399;
  font-size: 12px;
}

.unit {
  margin-left: 8px;
  color: #909399;
  font-size: 13px;
}
</style>

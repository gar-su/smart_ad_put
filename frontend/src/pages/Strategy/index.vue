<template>
  <div class="strategy-page">
    <el-row :gutter="20">
      <!-- 左侧：策略列表 -->
      <el-col :span="16">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>基建策略</span>
              <div>
                <el-select v-model="filterDimension" placeholder="筛选维度" clearable style="width: 120px; margin-right: 10px">
                  <el-option label="商品" value="product" />
                  <el-option label="广告单元" value="campaign" />
                </el-select>
                <el-button type="primary" @click="showAddDialog">添加策略</el-button>
              </div>
            </div>
          </template>

          <el-table :data="filteredRules" stripe style="width: 100%">
            <el-table-column prop="name" label="策略名称" width="180">
              <template #default="{ row }">
                <el-tag v-if="row.enabled" type="success" size="small">启用</el-tag>
                <el-tag v-else type="info" size="small">禁用</el-tag>
                {{ row.name }}
              </template>
            </el-table-column>
            <el-table-column prop="dimension" label="维度" width="100">
              <template #default="{ row }">
                <el-tag v-if="row.dimension === 'product'" type="primary">商品</el-tag>
                <el-tag v-else type="warning">广告单元</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="triggerStages" label="触发阶段" width="160">
              <template #default="{ row }">
                <el-tag
                  v-for="stage in row.triggerStages"
                  :key="stage"
                  size="small"
                  style="margin-right: 4px"
                >
                  {{ formatStage(stage) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="action" label="执行动作" width="120">
              <template #default="{ row }">
                <el-tag :type="getActionType(row.action)">
                  {{ formatAction(row.action) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="scale" label="规模" width="80">
              <template #default="{ row }">
                <span v-if="row.action === 'FOLLOW_UP'">—</span>
                <span v-else>{{ row.scale?.value || 0 }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button size="small" link type="primary" @click="editRule(row)">编辑</el-button>
                <el-button size="small" link type="danger" @click="deleteRule(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <!-- 决策日志预览 -->
        <el-card style="margin-top: 20px">
          <template #header>
            <span>最近决策预览</span>
            <el-button size="small" link type="primary" @click="$router.push('/decisions')">查看全部</el-button>
          </template>
          <el-table :data="recentDecisions" stripe size="small">
            <el-table-column prop="timestamp" label="时间" width="150">
              <template #default="{ row }">
                {{ formatTime(row.timestamp) }}
              </template>
            </el-table-column>
            <el-table-column prop="strategyName" label="策略" width="180" show-overflow-tooltip />
            <el-table-column prop="entityId" label="实体ID" width="120" show-overflow-tooltip />
            <el-table-column prop="entityStage" label="阶段" width="100">
              <template #default="{ row }">
                {{ formatStage(row.entityStage) }}
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <!-- 右侧：策略模板 & 统计 -->
      <el-col :span="8">
        <!-- 策略统计 -->
        <el-card>
          <template #header>
            <span>策略统计</span>
          </template>
          <div class="stats-grid">
            <div class="stat-item">
              <div class="stat-value">{{ stats.total }}</div>
              <div class="stat-label">总策略数</div>
            </div>
            <div class="stat-item">
              <div class="stat-value">{{ stats.enabled }}</div>
              <div class="stat-label">启用中</div>
            </div>
            <div class="stat-item">
              <div class="stat-value">{{ stats.todayTriggers }}</div>
              <div class="stat-label">今日触发</div>
            </div>
          </div>
        </el-card>

        <!-- 生命周期阶段说明 -->
        <el-card style="margin-top: 20px">
          <template #header>
            <span>阶段说明</span>
          </template>
          <div class="followup-hint">
            跟投档位（值得放量 → 发 FOLLOW_UP）：<el-tag size="small" type="success">成长期</el-tag><el-tag size="small" type="success">持续盈利</el-tag><el-tag size="small" type="success">入场期</el-tag><el-tag size="small" type="success">稳定期</el-tag>
          </div>
          <el-collapse>
            <el-collapse-item title="广告单元维度（8阶段）" name="campaign">
              <div class="stage-list">
                <div class="stage-item"><el-tag size="small" type="info">待观察</el-tag> 投放 &lt; 24h，时间不足</div>
                <div class="stage-item"><el-tag size="small" type="danger">冷死亡</el-tag> &gt;72h 从未产生收入</div>
                <div class="stage-item"><el-tag size="small" type="warning">冷启动</el-tag> 前24h ROI &lt; 10%</div>
                <div class="stage-item"><el-tag size="small" type="warning">验证期</el-tag> 24-72h ROI 10-40%</div>
                <div class="stage-item"><el-tag size="small" type="success">成长期</el-tag> ROI &gt; 40%（含6h快速通道）</div>
                <div class="stage-item"><el-tag size="small" type="success">持续盈利</el-tag> ROI &gt; 40% 超过7天</div>
                <div class="stage-item"><el-tag size="small" type="danger">衰退期</el-tag> ROI从高点下降 &gt; 50%</div>
                <div class="stage-item"><el-tag size="small" type="info">关停期</el-tag> ROI &lt; 10% 持续72h+</div>
              </div>
            </el-collapse-item>
            <el-collapse-item title="商品维度（6阶段）" name="product">
              <div class="stage-list">
                <div class="stage-item"><el-tag size="small" type="info">待观察</el-tag> 投放 &lt; 3天，时间不足</div>
                <div class="stage-item"><el-tag size="small" type="success">入场期</el-tag> 近3天ROI均值 &gt; 40%</div>
                <div class="stage-item"><el-tag size="small" type="success">稳定期</el-tag> 近5天ROI均在30-80%</div>
                <div class="stage-item"><el-tag size="small" type="success">成长期</el-tag> ROI &gt; 40% 且趋势上升</div>
                <div class="stage-item"><el-tag size="small" type="danger">衰退期</el-tag> ROI下滑 &gt; 30%</div>
                <div class="stage-item"><el-tag size="small" type="danger">退出期</el-tag> ROI &lt; 10% 持续5天</div>
              </div>
            </el-collapse-item>
          </el-collapse>
        </el-card>
      </el-col>
    </el-row>

    <!-- 添加/编辑策略对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="700px" :close-on-click-modal="false">
      <el-form :model="form" label-width="100px" :rules="formRules" ref="formRef">
        <el-form-item label="策略名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入策略名称" />
        </el-form-item>

        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="策略描述（可选）" />
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="维度" prop="dimension">
              <el-select v-model="form.dimension" placeholder="请选择维度" style="width: 100%">
                <el-option label="商品" value="product" />
                <el-option label="广告单元" value="campaign" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="触发阶段" prop="triggerStages">
          <el-select v-model="form.triggerStages" multiple placeholder="选择触发的生命周期阶段" style="width: 100%">
            <el-option-group v-if="form.dimension === 'product'" label="商品">
              <el-option label="待观察(<3天)" value="product_observing" />
              <el-option label="入场期(近3天ROI>40%)" value="product_entry" />
              <el-option label="稳定期(5天ROI均在30-80%)" value="product_sustained" />
              <el-option label="成长期(ROI>40%且上升)" value="product_growth" />
              <el-option label="衰退期(ROI下滑>30%)" value="product_decline" />
              <el-option label="退出期(ROI<10%)" value="product_exit" />
            </el-option-group>
            <el-option-group v-else label="广告单元">
              <el-option label="待观察(<24h)" value="campaign_observing" />
              <el-option label="冷死亡(>72h无收入)" value="campaign_cold_dead" />
              <el-option label="冷启动(ROI<10%)" value="campaign_cold_start" />
              <el-option label="验证期(ROI 10-40%)" value="campaign_verify" />
              <el-option label="成长期(ROI>40%)" value="campaign_growth" />
              <el-option label="持续盈利(>7天)" value="campaign_sustained" />
              <el-option label="衰退期" value="campaign_decline" />
              <el-option label="关停期" value="campaign_shutdown" />
            </el-option-group>
          </el-select>
        </el-form-item>

        <el-form-item label="执行动作" prop="action">
          <el-select v-model="form.action" placeholder="选择执行动作" style="width: 100%">
            <el-option-group label="增长期动作">
              <el-option label="饱和式攻击（批量创建广告）" value="GROWTH_BURST" />
              <el-option label="渠道扩张（复制到其他渠道）" value="CHANNEL_EXPAND" />
              <el-option label="复制广告" value="CLONE_AD" />
              <el-option label="增加预算" value="INCREASE_BUDGET" />
            </el-option-group>
            <el-option-group label="稳定期动作">
              <el-option label="预算平滑（调整预算分配）" value="BUDGET_SMOOTH" />
              <el-option label="素材预热（测试新素材）" value="MATERIAL_PREPARE" />
              <el-option label="维持现状" value="MAINTAIN" />
            </el-option-group>
            <el-option-group label="衰退期动作">
              <el-option label="有序关停" value="GRACEFUL_SHUTDOWN" />
              <el-option label="基建补充（重新创建）" value="REBUILD" />
              <el-option label="降低预算" value="REDUCE_BUDGET" />
            </el-option-group>
            <el-option-group label="跟投信号">
              <el-option label="跟投信号（判定值得投 → 下游新建放量任务）" value="FOLLOW_UP" />
            </el-option-group>
          </el-select>
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="执行规模">
              <el-input-number v-model="form.scale.value" :min="1" :max="form.scale.maxLimit" style="width: 100%" :disabled="form.action === 'FOLLOW_UP'" />
              <span v-if="form.action === 'FOLLOW_UP'" style="margin-left: 8px; color: #909399">跟投信号不带规模（下游模板承载）</span>
              <span v-else style="margin-left: 8px; color: #909399">条</span>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="额外条件">
          <div v-if="form.conditions.length === 0" class="condition-hint">
            无额外条件（仅根据阶段触发）
          </div>
          <div v-else v-for="(c, i) in form.conditions" :key="i" class="condition-row">
            <el-select v-model="c.field" placeholder="字段" style="width: 120px">
              <el-option label="前24h ROI" value="roi_0_24h" />
              <el-option label="总ROI" value="roi_total" />
              <el-option label="总收入" value="revenue" />
              <el-option label="总成本" value="cost" />
              <el-option label="总付费数" value="total_pays" />
              <el-option label="时长(小时)" value="duration_hours" />
            </el-select>
            <el-select v-model="c.operator" placeholder="操作符" style="width: 100px">
              <el-option label=">" value=">" />
              <el-option label="<" value="<" />
              <el-option label=">=" value=">=" />
              <el-option label="<=" value="<=" />
              <el-option label="==" value="==" />
            </el-select>
            <el-input-number v-model="c.value" placeholder="值" style="width: 120px" />
            <el-button @click="removeCondition(i)" type="danger" link>删除</el-button>
          </div>
          <el-button type="primary" plain size="small" @click="addCondition">+ 添加条件</el-button>
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="冷却时间">
              <el-input-number v-model="form.cooldownHours" :min="0" :max="168" style="width: 100%">
                <template #suffix>小时</template>
              </el-input-number>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-switch v-model="form.enabled" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveRule">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { ElMessage } from 'element-plus'

// 模拟数据
const filterDimension = ref('')

const rules = ref([
  {
    id: '1',
    name: '冷死亡-饱和攻击',
    description: 'Campaign收入为0时，饱和式攻击补充',
    dimension: 'campaign',
    triggerStages: ['campaign_cold_dead'],
    conditions: [],
    action: 'GROWTH_BURST',
    scale: { type: 'fixed', value: 50, maxLimit: 100 },
    cooldownHours: 24,
    enabled: true
  },
  {
    id: '2',
    name: '冷启动-复制策略',
    description: 'Campaign前24h ROI<10%时，复制新广告',
    dimension: 'campaign',
    triggerStages: ['campaign_cold_start'],
    conditions: [{ field: 'roi_0_24h', operator: '<', value: 0.1 }],
    action: 'CLONE_AD',
    scale: { type: 'fixed', value: 30, maxLimit: 50 },
    cooldownHours: 72,
    enabled: true
  },
  {
    id: '3',
    name: '成长期-增加预算',
    description: 'Campaign进入成长期(ROI>40%)时，增加预算',
    dimension: 'campaign',
    triggerStages: ['campaign_growth'],
    conditions: [{ field: 'roi_total', operator: '>=', value: 0.4 }],
    action: 'INCREASE_BUDGET',
    scale: { type: 'fixed', value: 20, maxLimit: 50 },
    cooldownHours: 12,
    enabled: true
  },
  {
    id: '4',
    name: '成长期-跟投',
    description: 'Campaign进入成长期(ROI>40%)，判定值得跟投，发跟投信号',
    dimension: 'campaign',
    triggerStages: ['campaign_growth'],
    conditions: [{ field: 'roi_total', operator: '>=', value: 0.4 }],
    action: 'FOLLOW_UP',
    scale: { type: 'fixed', value: 0, maxLimit: 0 },
    cooldownHours: 72,
    enabled: true
  },
  {
    id: '5',
    name: '持续盈利-跟投',
    description: 'Campaign持续盈利超7天，判定值得跟投',
    dimension: 'campaign',
    triggerStages: ['campaign_sustained'],
    conditions: [],
    action: 'FOLLOW_UP',
    scale: { type: 'fixed', value: 0, maxLimit: 0 },
    cooldownHours: 168,
    enabled: true
  },
  {
    id: '6',
    name: '盈利商品-跟投',
    description: '商品进入入场/成长/稳定期，判定值得跟投',
    dimension: 'product',
    triggerStages: ['product_entry', 'product_growth', 'product_sustained'],
    conditions: [],
    action: 'FOLLOW_UP',
    scale: { type: 'fixed', value: 0, maxLimit: 0 },
    cooldownHours: 24,
    enabled: true
  }
])

const recentDecisions = ref([
  {
    timestamp: '2026-04-20T10:30:00',
    strategyName: '冷启动-复制策略',
    entityId: 'campaign_001',
    entityStage: 'campaign_cold_start',
  },
  {
    timestamp: '2026-04-20T09:15:00',
    strategyName: '成长期-增加预算',
    entityId: 'campaign_456',
    entityStage: 'campaign_growth',
  }
])

const stats = computed(() => ({
  total: rules.value.length,
  enabled: rules.value.filter(r => r.enabled).length,
  todayTriggers: 12,
}))

// 计算属性
const filteredRules = computed(() => {
  if (!filterDimension.value) return rules.value
  return rules.value.filter(r => r.dimension === filterDimension.value)
})

// 对话框
const dialogVisible = ref(false)
const dialogTitle = ref('添加策略')
const editingId = ref<string | null>(null)
const formRef = ref()

const defaultForm = () => ({
  name: '',
  description: '',
  dimension: 'product',
  triggerStages: [] as string[],
  conditions: [] as { field: string; operator: string; value: number }[],
  action: 'GROWTH_BURST',
  scale: { type: 'fixed', value: 10, maxLimit: 100 },
  cooldownHours: 24,
  enabled: true
})

const form = reactive(defaultForm())

const formRules = {
  name: [{ required: true, message: '请输入策略名称', trigger: 'blur' }],
  dimension: [{ required: true, message: '请选择维度', trigger: 'change' }],
  triggerStages: [{ required: true, message: '请选择触发阶段', trigger: 'change' }],
  action: [{ required: true, message: '请选择执行动作', trigger: 'change' }]
}

// 方法
function formatStage(stage: string) {
  const map: Record<string, string> = {
    // Campaign维度（基于ROI）
    'campaign_observing': '待观察(<24h)',
    'campaign_cold_dead': '冷死亡(>72h无收入)',
    'campaign_cold_start': '冷启动(ROI<10%)',
    'campaign_verify': '验证期(ROI 10-40%)',
    'campaign_growth': '成长期(ROI>40%)',
    'campaign_sustained': '持续盈利(>7天)',
    'campaign_decline': '衰退期',
    'campaign_shutdown': '关停期',
    // Product维度（基于回测数据）
    'product_observing': '待观察(<3天)',
    'product_entry': '入场期(近3天ROI>40%)',
    'product_sustained': '稳定期(5天ROI均30-80%)',
    'product_growth': '成长期(ROI>40%上升)',
    'product_decline': '衰退期(下滑>30%)',
    'product_exit': '退出期(ROI<10%)',
  }
  return map[stage] || stage
}

function formatAction(action: string) {
  const map: Record<string, string> = {
    'GROWTH_BURST': '饱和攻击',
    'CHANNEL_EXPAND': '渠道扩张',
    'CLONE_AD': '复制广告',
    'BUDGET_SMOOTH': '预算平滑',
    'MATERIAL_PREPARE': '素材预热',
    'GRACEFUL_SHUTDOWN': '有序关停',
    'REBUILD': '基建补充',
    'INCREASE_BUDGET': '增加预算',
    'REDUCE_BUDGET': '降低预算',
    'MAINTAIN': '维持现状',
    'FOLLOW_UP': '跟投信号'
  }
  return map[action] || action
}

function getActionType(action: string) {
  const map: Record<string, string> = {
    'GROWTH_BURST': 'success',
    'CHANNEL_EXPAND': 'success',
    'CLONE_AD': 'primary',
    'INCREASE_BUDGET': 'success',
    'BUDGET_SMOOTH': 'warning',
    'MATERIAL_PREPARE': 'warning',
    'MAINTAIN': 'info',
    'GRACEFUL_SHUTDOWN': 'danger',
    'REBUILD': 'danger',
    'REDUCE_BUDGET': 'warning',
    'FOLLOW_UP': 'success'
  }
  return map[action] || 'info'
}

function formatTime(time: string) {
  return new Date(time).toLocaleString('zh-CN')
}

function showAddDialog() {
  dialogTitle.value = '添加策略'
  editingId.value = null
  Object.assign(form, defaultForm())
  dialogVisible.value = true
}

function editRule(row: any) {
  dialogTitle.value = '编辑策略'
  editingId.value = row.id
  Object.assign(form, JSON.parse(JSON.stringify(row)))
  dialogVisible.value = true
}

function addCondition() {
  form.conditions.push({ field: 'roi_0_24h', operator: '<', value: 0 })
}

function removeCondition(index: number) {
  form.conditions.splice(index, 1)
}

function saveRule() {
  if (!form.name || form.triggerStages.length === 0) {
    ElMessage.warning('请填写完整信息')
    return
  }

  if (editingId.value) {
    const idx = rules.value.findIndex(r => r.id === editingId.value)
    if (idx !== -1) {
      rules.value[idx] = { ...form, id: editingId.value }
    }
    ElMessage.success('策略已更新')
  } else {
    rules.value.push({ ...form, id: Date.now().toString() })
  }

  dialogVisible.value = false
}

function deleteRule(row: any) {
  const idx = rules.value.findIndex(r => r.id === row.id)
  if (idx !== -1) {
    rules.value.splice(idx, 1)
  }
  ElMessage.success('策略已删除')
}

</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 15px;
}

.stat-item {
  text-align: center;
  padding: 15px;
  background: #f5f7fa;
  border-radius: 4px;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #409eff;
}

.stat-label {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.stage-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stage-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.condition-row {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
  align-items: center;
}

.condition-hint {
  color: #909399;
  font-size: 13px;
}

.followup-hint {
  font-size: 13px;
  color: #606266;
  margin-bottom: 10px;
  line-height: 24px;
}

.followup-hint .el-tag {
  margin-right: 4px;
}
</style>

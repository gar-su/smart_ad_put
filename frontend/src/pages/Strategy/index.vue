<template>
  <div class="strategy-page">
    <el-row :gutter="20">
      <!-- 左侧：规则列表 -->
      <el-col :span="16">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>基建策略规则</span>
              <div>
                <el-select v-model="filterDimension" placeholder="筛选维度" clearable style="width: 120px; margin-right: 10px">
                  <el-option label="商品" value="product" />
                  <el-option label="广告单元" value="campaign" />
                </el-select>
                <el-button type="primary" @click="showAddDialog">添加规则</el-button>
              </div>
            </div>
          </template>

          <el-table :data="filteredRules" stripe style="width: 100%">
            <el-table-column prop="name" label="规则名称" width="180">
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
                {{ row.scale?.value || 0 }}
              </template>
            </el-table-column>
            <el-table-column prop="priority" label="优先级" width="80" />
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
            <el-table-column prop="entityId" label="实体ID" width="120" show-overflow-tooltip />
            <el-table-column prop="entityStage" label="阶段" width="100">
              <template #default="{ row }">
                {{ formatStage(row.entityStage) }}
              </template>
            </el-table-column>
            <el-table-column prop="action" label="动作">
              <template #default="{ row }">
                {{ formatAction(row.action) }}
              </template>
            </el-table-column>
            <el-table-column prop="scale" label="规模" width="60" />
          </el-table>
        </el-card>
      </el-col>

      <!-- 右侧：策略模板 & 统计 -->
      <el-col :span="8">
        <!-- 策略模板 -->
        <el-card>
          <template #header>
            <span>策略模板</span>
          </template>
          <div class="template-list">
            <div
              v-for="template in templates"
              :key="template.id"
              class="template-item"
              @click="applyTemplate(template)"
            >
              <div class="template-name">{{ template.name }}</div>
              <div class="template-desc">{{ template.description }}</div>
            </div>
          </div>
        </el-card>

        <!-- 策略统计 -->
        <el-card style="margin-top: 20px">
          <template #header>
            <span>策略统计</span>
          </template>
          <div class="stats-grid">
            <div class="stat-item">
              <div class="stat-value">{{ stats.total }}</div>
              <div class="stat-label">总规则数</div>
            </div>
            <div class="stat-item">
              <div class="stat-value">{{ stats.enabled }}</div>
              <div class="stat-label">启用中</div>
            </div>
            <div class="stat-item">
              <div class="stat-value">{{ stats.todayTriggers }}</div>
              <div class="stat-label">今日触发</div>
            </div>
            <div class="stat-item">
              <div class="stat-value">{{ stats.decisionsThisWeek }}</div>
              <div class="stat-label">本周决策</div>
            </div>
          </div>
        </el-card>

        <!-- 生命周期阶段说明 -->
        <el-card style="margin-top: 20px">
          <template #header>
            <span>阶段说明</span>
          </template>
          <el-collapse>
            <el-collapse-item title="商品维度" name="product">
              <div class="stage-list">
                <div class="stage-item"><el-tag size="small">引入期</el-tag> 上架时间短</div>
                <div class="stage-item"><el-tag size="small" type="success">成长期</el-tag> 消耗增长 >20%</div>
                <div class="stage-item"><el-tag size="small" type="warning">成熟期</el-tag> 消耗稳定</div>
                <div class="stage-item"><el-tag size="small" type="danger">衰退期</el-tag> 消耗下降 >30%</div>
                <div class="stage-item"><el-tag size="small" type="info">冷启动</el-tag> 首日消耗低</div>
              </div>
            </el-collapse-item>
            <el-collapse-item title="广告单元维度" name="campaign">
              <div class="stage-list">
                <div class="stage-item"><el-tag size="small" type="danger">冷死亡</el-tag> 24h内死亡</div>
                <div class="stage-item"><el-tag size="small" type="info">冷启动</el-tag> 存活但短期</div>
                <div class="stage-item"><el-tag size="small" type="success">增长期</el-tag> 消耗增长</div>
                <div class="stage-item"><el-tag size="small" type="warning">稳定期</el-tag> 消耗稳定</div>
                <div class="stage-item"><el-tag size="small" type="danger">衰退期</el-tag> 消耗下降</div>
                <div class="stage-item"><el-tag size="small" type="info">关停期</el-tag> 即将停止</div>
              </div>
            </el-collapse-item>
          </el-collapse>
        </el-card>
      </el-col>
    </el-row>

    <!-- 添加/编辑规则对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="700px" :close-on-click-modal="false">
      <el-form :model="form" label-width="100px" :rules="formRules" ref="formRef">
        <el-form-item label="规则名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入规则名称" />
        </el-form-item>

        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="规则描述（可选）" />
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
          <el-col :span="12">
            <el-form-item label="优先级" prop="priority">
              <el-input-number v-model="form.priority" :min="1" :max="1000" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="触发阶段" prop="triggerStages">
          <el-select v-model="form.triggerStages" multiple placeholder="选择触发的生命周期阶段" style="width: 100%">
            <el-option-group v-if="form.dimension === 'product'" label="商品">
              <el-option label="引入期" value="product_introducing" />
              <el-option label="成长期" value="product_growth" />
              <el-option label="成熟期" value="product_mature" />
              <el-option label="衰退期" value="product_decline" />
              <el-option label="冷启动失败" value="product_cold_start" />
            </el-option-group>
            <el-option-group v-else label="广告单元">
              <el-option label="冷死亡" value="campaign_cold_dead" />
              <el-option label="冷启动" value="campaign_cold_start" />
              <el-option label="增长期" value="campaign_growth" />
              <el-option label="稳定期" value="campaign_stable" />
              <el-option label="衰退期" value="campaign_decay" />
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
            </el-option-group>
            <el-option-group label="稳定期动作">
              <el-option label="预算平滑（调整预算分配）" value="BUDGET_SMOOTH" />
              <el-option label="素材预热（测试新素材）" value="MATERIAL_PREPARE" />
            </el-option-group>
            <el-option-group label="衰退期动作">
              <el-option label="有序关停" value="GRACEFUL_SHUTDOWN" />
              <el-option label="基建补充（重新创建）" value="REBUILD" />
            </el-option-group>
          </el-select>
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="执行规模">
              <el-input-number v-model="form.scale.value" :min="1" :max="form.scale.maxLimit" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="最小置信度">
              <el-slider v-model="form.confidenceMin" :min="0" :max="1" :step="0.1" show-input />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="额外条件">
          <div v-if="form.conditions.length === 0" class="condition-hint">
            无额外条件（仅根据阶段触发）
          </div>
          <div v-else v-for="(c, i) in form.conditions" :key="i" class="condition-row">
            <el-select v-model="c.field" placeholder="字段" style="width: 120px">
              <el-option label="首日消耗" value="cost_first_24h" />
              <el-option label="消耗变化" value="cost_change_pct" />
              <el-option label="总付费数" value="total_pays" />
              <el-option label="CTR" value="ctr" />
              <el-option label="时长" value="duration" />
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
    name: '冷启动失败-饱和攻击',
    description: '商品冷启动失败时，自动饱和式攻击补充流量',
    dimension: 'product',
    triggerStages: ['product_cold_start'],
    conditions: [{ field: 'cost_first_24h', operator: '<', value: 50 }],
    action: 'GROWTH_BURST',
    scale: { type: 'fixed', value: 50, maxLimit: 100 },
    confidenceMin: 0.7,
    priority: 10,
    cooldownHours: 24,
    enabled: true
  },
  {
    id: '2',
    name: '衰退期-基建补充',
    description: '商品进入衰退期时，自动启动新一轮基建',
    dimension: 'product',
    triggerStages: ['product_decline'],
    conditions: [{ field: 'total_pays', operator: '>=', value: 10 }],
    action: 'REBUILD',
    scale: { type: 'fixed', value: 30, maxLimit: 50 },
    confidenceMin: 0.8,
    priority: 20,
    cooldownHours: 72,
    enabled: true
  },
  {
    id: '3',
    name: '冷死亡-复制替换',
    description: 'Campaign冷启动死亡时，自动复制新广告替换',
    dimension: 'campaign',
    triggerStages: ['campaign_cold_dead'],
    conditions: [],
    action: 'CLONE_AD',
    scale: { type: 'fixed', value: 5, maxLimit: 10 },
    confidenceMin: 0.85,
    priority: 15,
    cooldownHours: 12,
    enabled: true
  }
])

const recentDecisions = ref([
  {
    timestamp: '2026-04-20T10:30:00',
    entityId: 'short_play_001',
    entityStage: 'product_cold_start',
    action: 'GROWTH_BURST',
    scale: 50
  },
  {
    timestamp: '2026-04-20T09:15:00',
    entityId: 'campaign_123',
    entityStage: 'campaign_cold_dead',
    action: 'CLONE_AD',
    scale: 5
  }
])

const templates = ref([
  {
    id: 'tpl_cold_start',
    name: '冷启动失败策略',
    description: '商品首日消耗<50元时，触发饱和式攻击'
  },
  {
    id: 'tpl_decline',
    name: '衰退期策略',
    description: '商品进入衰退期时，自动基建补充'
  },
  {
    id: 'tpl_growth',
    name: '成长期策略',
    description: '商品进入成长期时，渠道扩张'
  },
  {
    id: 'tpl_campaign_death',
    name: 'Campaign死亡策略',
    description: 'Campaign死亡时自动复制替换'
  }
])

const stats = reactive({
  total: 3,
  enabled: 2,
  todayTriggers: 12,
  decisionsThisWeek: 156
})

// 计算属性
const filteredRules = computed(() => {
  if (!filterDimension.value) return rules.value
  return rules.value.filter(r => r.dimension === filterDimension.value)
})

// 对话框
const dialogVisible = ref(false)
const dialogTitle = ref('添加规则')
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
  confidenceMin: 0.7,
  priority: 100,
  cooldownHours: 24,
  enabled: true
})

const form = reactive(defaultForm())

const formRules = {
  name: [{ required: true, message: '请输入规则名称', trigger: 'blur' }],
  dimension: [{ required: true, message: '请选择维度', trigger: 'change' }],
  triggerStages: [{ required: true, message: '请选择触发阶段', trigger: 'change' }],
  action: [{ required: true, message: '请选择执行动作', trigger: 'change' }]
}

// 方法
function formatStage(stage: string) {
  const map: Record<string, string> = {
    'product_introducing': '引入期',
    'product_growth': '成长期',
    'product_mature': '成熟期',
    'product_decline': '衰退期',
    'product_cold_start': '冷启动',
    'campaign_cold_dead': '冷死亡',
    'campaign_cold_start': '冷启动',
    'campaign_growth': '增长期',
    'campaign_stable': '稳定期',
    'campaign_decay': '衰退期',
    'campaign_shutdown': '关停期'
  }
  return map[stage] || stage
}

function formatAction(action: string) {
  const map: Record<string, string> = {
    'GROWTH_BURST': '饱和攻击',
    'CHANNEL_EXPAND': '渠道扩张',
    'CLONE_AD': '复制',
    'BUDGET_SMOOTH': '预算平滑',
    'MATERIAL_PREPARE': '素材预热',
    'GRACEFUL_SHUTDOWN': '关停',
    'REBUILD': '重建'
  }
  return map[action] || action
}

function getActionType(action: string) {
  const map: Record<string, string> = {
    'GROWTH_BURST': 'success',
    'CHANNEL_EXPAND': 'success',
    'CLONE_AD': 'primary',
    'BUDGET_SMOOTH': 'warning',
    'MATERIAL_PREPARE': 'warning',
    'GRACEFUL_SHUTDOWN': 'danger',
    'REBUILD': 'danger'
  }
  return map[action] || 'info'
}

function formatTime(time: string) {
  return new Date(time).toLocaleString('zh-CN')
}

function showAddDialog() {
  dialogTitle.value = '添加规则'
  editingId.value = null
  Object.assign(form, defaultForm())
  dialogVisible.value = true
}

function editRule(row: any) {
  dialogTitle.value = '编辑规则'
  editingId.value = row.id
  Object.assign(form, JSON.parse(JSON.stringify(row)))
  dialogVisible.value = true
}

function addCondition() {
  form.conditions.push({ field: 'cost_first_24h', operator: '<', value: 0 })
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
    ElMessage.success('规则已更新')
  } else {
    rules.value.push({ ...form, id: Date.now().toString() })
    stats.total++
  }

  dialogVisible.value = false
}

function deleteRule(row: any) {
  const idx = rules.value.findIndex(r => r.id === row.id)
  if (idx !== -1) {
    rules.value.splice(idx, 1)
    stats.total--
  }
  ElMessage.success('规则已删除')
}

function applyTemplate(template: any) {
  const templateMap: Record<string, any> = {
    'tpl_cold_start': {
      name: '冷启动失败策略',
      dimension: 'product',
      triggerStages: ['product_cold_start'],
      conditions: [{ field: 'cost_first_24h', operator: '<', value: 50 }],
      action: 'GROWTH_BURST',
      scale: { type: 'fixed', value: 50, maxLimit: 100 },
      priority: 10,
      cooldownHours: 24
    },
    'tpl_decline': {
      name: '衰退期策略',
      dimension: 'product',
      triggerStages: ['product_decline'],
      conditions: [{ field: 'total_pays', operator: '>=', value: 10 }],
      action: 'REBUILD',
      scale: { type: 'fixed', value: 30, maxLimit: 50 },
      priority: 20,
      cooldownHours: 72
    },
    'tpl_growth': {
      name: '成长期策略',
      dimension: 'product',
      triggerStages: ['product_growth'],
      conditions: [],
      action: 'CHANNEL_EXPAND',
      scale: { type: 'fixed', value: 20, maxLimit: 30 },
      priority: 30,
      cooldownHours: 48
    },
    'tpl_campaign_death': {
      name: 'Campaign死亡策略',
      dimension: 'campaign',
      triggerStages: ['campaign_cold_dead'],
      conditions: [],
      action: 'CLONE_AD',
      scale: { type: 'fixed', value: 5, maxLimit: 10 },
      priority: 15,
      cooldownHours: 12
    }
  }

  const config = templateMap[template.id]
  if (config) {
    Object.assign(form, { ...defaultForm(), ...config, enabled: true })
    dialogTitle.value = '添加规则'
    editingId.value = null
    dialogVisible.value = true
  }
}
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.template-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.template-item {
  padding: 12px;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.3s;
}

.template-item:hover {
  border-color: #409eff;
  background: #f5f7fa;
}

.template-name {
  font-weight: 500;
  margin-bottom: 4px;
}

.template-desc {
  font-size: 12px;
  color: #909399;
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
</style>

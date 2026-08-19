<template>
  <div class="decisions-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>决策日志</span>
          <div>
            <el-select
              v-model="filterType"
              placeholder="筛选类型"
              clearable
              style="width: 150px; margin-right: 10px"
            >
              <el-option label="跟投信号" value="FOLLOW_UP" />
              <el-option label="创建广告" value="CREATE_AD" />
              <el-option label="复制广告" value="CLONE_AD" />
              <el-option label="调整预算" value="ADJUST_BUDGET" />
              <el-option label="停止广告" value="STOP_AD" />
            </el-select>
            <el-button type="primary" @click="refresh">刷新</el-button>
          </div>
        </div>
      </template>

      <el-table :data="filteredDecisions" stripe style="width: 100%">
        <el-table-column prop="timestamp" label="时间" width="180" />
        <el-table-column prop="type" label="决策类型" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.type === 'FOLLOW_UP'" type="success">跟投信号</el-tag>
            <el-tag v-else-if="row.type === 'CREATE_AD'">创建广告</el-tag>
            <el-tag v-else-if="row.type === 'CLONE_AD'">复制广告</el-tag>
            <el-tag v-else-if="row.type === 'PAUSE_AD'">暂停广告</el-tag>
            <el-tag v-else-if="row.type === 'STOP_AD'">停止广告</el-tag>
            <el-tag v-else-if="row.type === 'ADJUST_BUDGET'">调整预算</el-tag>
            <el-tag v-else type="info">{{ row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="strategy_name" label="策略" width="180" show-overflow-tooltip />
        <el-table-column prop="dimension" label="维度" width="90" />
        <el-table-column prop="target_id" label="目标ID" width="180" show-overflow-tooltip />
        <el-table-column label="跟投信号" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <template v-if="row.type === 'FOLLOW_UP'">
              <span class="signal-id">{{ row.signal_id }}</span>
              <el-tag size="small" type="info" style="margin-left: 4px">{{ row.language_code || '-' }}</el-tag>
              <el-tag size="small" v-if="row.script_no" type="warning" style="margin-left: 4px">{{ row.script_no }}</el-tag>
            </template>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column prop="action" label="动作" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.action === 'FOLLOW_UP'" type="success">跟投信号</el-tag>
            <el-tag v-else-if="row.action === 'GROWTH_BURST'" type="success">饱和攻击</el-tag>
            <el-tag v-else-if="row.action === 'CHANNEL_EXPAND'" type="success">渠道扩张</el-tag>
            <el-tag v-else-if="row.action === 'CLONE_AD'" type="primary">复制广告</el-tag>
            <el-tag v-else-if="row.action === 'BUDGET_SMOOTH'" type="warning">预算平滑</el-tag>
            <el-tag v-else-if="row.action === 'MATERIAL_PREPARE'" type="warning">素材预热</el-tag>
            <el-tag v-else-if="row.action === 'INCREASE_BUDGET'" type="success">增加预算</el-tag>
            <el-tag v-else-if="row.action === 'REDUCE_BUDGET'" type="warning">降低预算</el-tag>
            <el-tag v-else-if="row.action === 'MAINTAIN'" type="info">维持现状</el-tag>
            <el-tag v-else-if="row.action === 'GRACEFUL_SHUTDOWN'" type="danger">有序关停</el-tag>
            <el-tag v-else-if="row.action === 'REBUILD'" type="danger">基建补充</el-tag>
            <el-tag v-else>{{ row.action }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="详情" width="80">
          <template #default="{ row }">
            <el-button size="small" @click="showDetail(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="currentPage"
        :page-size="20"
        :total="total"
        layout="total, prev, pager, next"
        style="margin-top: 20px; justify-content: center"
      />
    </el-card>

    <el-dialog v-model="detailVisible" title="决策详情" width="600px">
      <pre>{{ detailContent }}</pre>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'

const mockDecisions = [
  { timestamp: '2026-04-20 14:30:00', type: 'CREATE_AD', dimension: 'campaign', target_id: 'campaign_005_abc123def456', action: 'GROWTH_BURST', strategy_name: '冷死亡-饱和攻击策略' },
  { timestamp: '2026-04-20 14:05:00', type: 'FOLLOW_UP', dimension: 'campaign', target_id: 'campaign_456_mno345', action: 'FOLLOW_UP', strategy_name: '成长期-跟投策略', signal_id: '202604201405_campaign_456', language_code: 'en', script_no: '' },
  { timestamp: '2026-04-20 13:50:00', type: 'ADJUST_BUDGET', dimension: 'campaign', target_id: 'campaign_456_mno345', action: 'INCREASE_BUDGET', strategy_name: '成长期-增加预算策略' },
  { timestamp: '2026-04-20 13:20:00', type: 'STOP_AD', dimension: 'campaign', target_id: 'campaign_789_pqr678', action: 'GRACEFUL_SHUTDOWN', strategy_name: '衰退期-有序关停策略' },
  { timestamp: '2026-04-20 13:00:00', type: 'FOLLOW_UP', dimension: 'product', target_id: 'product_010_ghi901', action: 'FOLLOW_UP', strategy_name: '盈利商品-跟投策略', signal_id: '202604201300_product_010', language_code: 'es', script_no: 'LA001' },
  { timestamp: '2026-04-20 12:45:00', type: 'CREATE_AD', dimension: 'product', target_id: 'product_010_ghi901', action: 'REBUILD', strategy_name: '商品亏损-基建补充策略' },
]

const decisions = ref<any[]>([...mockDecisions])
const filterType = ref('')
const currentPage = ref(1)
const total = ref(mockDecisions.length)
const detailVisible = ref(false)
const detailContent = ref('')

const filteredDecisions = computed(() => {
  if (!filterType.value) return decisions.value
  return decisions.value.filter(d => d.type === filterType.value)
})

function refresh() {
  decisions.value = [...mockDecisions]
  total.value = mockDecisions.length
  currentPage.value = 1
  ElMessage.success('刷新成功')
}

function showDetail(row: any) {
  detailContent.value = JSON.stringify(row, null, 2)
  detailVisible.value = true
}
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.signal-id {
  font-family: monospace;
  font-size: 12px;
  color: #606266;
}

pre {
  background: #f5f7fa;
  padding: 15px;
  border-radius: 4px;
  overflow-x: auto;
}
</style>

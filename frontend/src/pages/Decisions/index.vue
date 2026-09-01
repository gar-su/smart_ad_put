<template>
  <div class="decisions-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>决策日志（建造信号）</span>
          <div>
            <el-select
              v-model="filterType"
              placeholder="筛选类型"
              clearable
              style="width: 150px; margin-right: 10px"
            >
              <el-option label="跟投信号" value="FOLLOW_UP" />
            </el-select>
            <el-button type="primary" @click="refresh">刷新</el-button>
          </div>
        </div>
      </template>

      <el-empty v-if="!filteredDecisions.length" description="暂无信号" />
      <el-table v-else :data="filteredDecisions" stripe style="width: 100%">
        <el-table-column prop="timestamp" label="时间" width="180" show-overflow-tooltip />
        <el-table-column prop="signal_type" label="信号类型" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.signal_type === 'FOLLOW_UP'" type="success">跟投信号</el-tag>
            <el-tag v-else>{{ row.signal_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="target_dimension" label="维度" width="90" />
        <el-table-column prop="target_id" label="目标ID" width="180" show-overflow-tooltip />
        <el-table-column prop="shortplay_name" label="短剧名" min-width="140" show-overflow-tooltip />
        <el-table-column label="语言/剧本" width="150">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.language_code || '-' }}</el-tag>
            <el-tag size="small" v-if="row.script_no" type="warning" style="margin-left: 4px">{{ row.script_no }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="confidence" label="置信度" width="90" align="right">
          <template #default="{ row }">{{ (Number(row.confidence) * 100).toFixed(0) }}%</template>
        </el-table-column>
        <el-table-column prop="reason" label="原因" min-width="200" show-overflow-tooltip />
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

    <el-dialog v-model="detailVisible" title="信号详情" width="600px">
      <pre>{{ detailContent }}</pre>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

// 与 BuildSignal 契约一致的示例数据（后端不可达时兜底展示）
const mockSignals = [
  {
    signal_id: '20260831161414_2041056509957242881',
    signal_type: 'FOLLOW_UP',
    target_dimension: 'product',
    target_id: '2041056509957242881',
    language_code: '马来西亚语',
    script_no: 'LA011',
    shortplay_name: 'The Discarded Ace',
    reason: '成长期: ROI>175.0% 且趋势上升71%',
    confidence: 0.87,
    timestamp: '2026-08-31T16:14:14Z',
  },
  {
    signal_id: '20260831161246_2039571882456613872',
    signal_type: 'FOLLOW_UP',
    target_dimension: 'product',
    target_id: '2039571882456613872',
    language_code: '印尼语',
    script_no: 'LA007',
    shortplay_name: 'Her Hidden Love',
    reason: '入场期: 近3天ROI均值>40%',
    confidence: 0.74,
    timestamp: '2026-08-31T16:12:46Z',
  },
  {
    signal_id: '20260831160802_campaign_108',
    signal_type: 'FOLLOW_UP',
    target_dimension: 'campaign',
    target_id: 'campaign_108_mno208',
    language_code: '英语',
    script_no: 'LA103',
    shortplay_name: 'The Wolf in the Fog',
    reason: '成长期Campaign: ROI>40% 持续上升',
    confidence: 0.81,
    timestamp: '2026-08-31T16:08:02Z',
  },
]

const decisions = ref<any[]>([])
const filterType = ref('')
const currentPage = ref(1)
const total = ref(0)
const detailVisible = ref(false)
const detailContent = ref('')

const filteredDecisions = computed(() => {
  if (!filterType.value) return decisions.value
  return decisions.value.filter(d => d.signal_type === filterType.value)
})

async function refresh() {
  try {
    const res = await fetch('/api/signals')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    decisions.value = data.signals ?? []
    total.value = data.total ?? decisions.value.length
    currentPage.value = 1
    ElMessage.success('刷新成功')
  } catch {
    decisions.value = [...mockSignals]
    total.value = mockSignals.length
    currentPage.value = 1
    ElMessage.warning('后端未连接，展示示例数据')
  }
}

function showDetail(row: any) {
  detailContent.value = JSON.stringify(row, null, 2)
  detailVisible.value = true
}

onMounted(refresh)
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

pre {
  background: #f5f7fa;
  padding: 15px;
  border-radius: 4px;
  overflow-x: auto;
}
</style>
<template>
  <div class="decisions-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <div class="title-group">
            <span>决策日志（建造信号）</span>
            <span class="mock-tag">前端示例数据</span>
          </div>
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
      <el-table v-else :data="pagedDecisions" stripe style="width: 100%">
        <el-table-column prop="timestamp" label="时间" width="180" show-overflow-tooltip />
        <el-table-column prop="signal_type" label="信号类型" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.signal_type === 'FOLLOW_UP'" type="success">跟投信号</el-tag>
            <el-tag v-else>{{ row.signal_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="维度" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.target_dimension === 'product'" type="success" size="small">短剧</el-tag>
            <el-tag v-else type="primary" size="small">广告单元</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="target_id" label="目标ID" width="180" show-overflow-tooltip />
        <el-table-column prop="shortplay_name" label="短剧名" min-width="140" show-overflow-tooltip />
        <el-table-column label="语言/剧本" width="150">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.language_code || '-' }}</el-tag>
            <el-tag size="small" v-if="row.script_no" type="warning" style="margin-left: 4px">{{ row.script_no }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="confidence" label="置信度" width="110" align="right">
          <template #header>
            <el-tooltip content="阶段判定可信度（0-100%）：数据越充分、规则越明确，置信度越高。非盈利概率。" placement="top">
              <span>置信度 <el-icon style="vertical-align: middle"><QuestionFilled /></el-icon></span>
            </el-tooltip>
          </template>
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
        :page-size="PAGE_SIZE"
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
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { QuestionFilled } from '@element-plus/icons-vue'

// 前端 mock：不请求后端，页面数据源即此处示例数据（与 BuildSignal 契约一致）
const MOCK_SIGNALS = [
  { signal_id: '20260907161414_2041056509957242881', signal_type: 'FOLLOW_UP', target_dimension: 'product', target_id: '2041056509957242881', language_code: '马来西亚语', script_no: 'LA011', shortplay_name: 'The Discarded Ace', reason: '成长期: ROI>175.0% 且趋势上升71%', confidence: 0.87, timestamp: '2026-09-07T16:14:14Z' },
  { signal_id: '20260907161246_2039571882456613872', signal_type: 'FOLLOW_UP', target_dimension: 'product', target_id: '2039571882456613872', language_code: '印尼语', script_no: 'LA007', shortplay_name: 'Her Hidden Love', reason: '入场期: 近3天ROI均值>40%', confidence: 0.74, timestamp: '2026-09-07T16:12:46Z' },
  { signal_id: '20260907160802_campaign_108', signal_type: 'FOLLOW_UP', target_dimension: 'campaign', target_id: 'campaign_108_mno208', language_code: '英语', script_no: 'LA103', shortplay_name: 'The Wolf in the Fog', reason: '成长期Campaign: ROI>40% 持续上升', confidence: 0.81, timestamp: '2026-09-07T16:08:02Z' },
  { signal_id: '20260907115510_2041877302345568256', signal_type: 'FOLLOW_UP', target_dimension: 'product', target_id: '2041877302345568256', language_code: '泰语', script_no: 'LA045', shortplay_name: 'My Billionaire Ex', reason: '稳定期: ROI 45% 且波动平缓', confidence: 0.79, timestamp: '2026-09-07T11:55:10Z' },
  { signal_id: '20260907094233_2042991100348817408', signal_type: 'FOLLOW_UP', target_dimension: 'product', target_id: '2042991100348817408', language_code: '越南语', script_no: 'LA062', shortplay_name: "The CEO's Secret Bride", reason: '成长期: ROI>120% 且趋势上升35%', confidence: 0.83, timestamp: '2026-09-07T09:42:33Z' },
  { signal_id: '20260906221005_campaign_233', signal_type: 'FOLLOW_UP', target_dimension: 'campaign', target_id: 'campaign_233_mno118', language_code: '西班牙语', script_no: 'LA210', shortplay_name: 'Reborn as the Heiress', reason: '持续盈利Campaign: ROI>40% 已持续7天', confidence: 0.85, timestamp: '2026-09-06T22:10:05Z' },
  { signal_id: '20260906183147_2043310298817762048', signal_type: 'FOLLOW_UP', target_dimension: 'product', target_id: '2043310298817762048', language_code: '印尼语', script_no: 'LA019', shortplay_name: 'The Substitute Wife', reason: '入场期: 近3天ROI均值>40%', confidence: 0.71, timestamp: '2026-09-06T18:31:47Z' },
  { signal_id: '20260906150219_2044118822013345792', signal_type: 'FOLLOW_UP', target_dimension: 'product', target_id: '2044118822013345792', language_code: '英语', script_no: 'LA088', shortplay_name: "Alpha's Rejected Mate", reason: '成长期: ROI>95% 且趋势上升28%', confidence: 0.8, timestamp: '2026-09-06T15:02:19Z' },
  { signal_id: '20260906103356_2044550129388412928', signal_type: 'FOLLOW_UP', target_dimension: 'product', target_id: '2044550129388412928', language_code: '马来西亚语', script_no: 'LA033', shortplay_name: 'Marry Me, Stranger', reason: '稳定期: ROI 52% 且波动平缓', confidence: 0.77, timestamp: '2026-09-06T10:33:56Z' },
  { signal_id: '20260905224410_campaign_097', signal_type: 'FOLLOW_UP', target_dimension: 'campaign', target_id: 'campaign_097_mno204', language_code: '泰语', script_no: 'LA156', shortplay_name: "The Nanny's Secret", reason: '成长期Campaign: ROI>40% 持续上升', confidence: 0.78, timestamp: '2026-09-05T22:44:10Z' },
  { signal_id: '20260905181122_2045093388012273664', signal_type: 'FOLLOW_UP', target_dimension: 'product', target_id: '2045093388012273664', language_code: '越南语', script_no: 'LA071', shortplay_name: 'Divorced, Not Broken', reason: '成长期: ROI>110% 且趋势上升19%', confidence: 0.76, timestamp: '2026-09-05T18:11:22Z' },
  { signal_id: '20260905142605_2045662011772883456', signal_type: 'FOLLOW_UP', target_dimension: 'product', target_id: '2045662011772883456', language_code: '印尼语', script_no: 'LA024', shortplay_name: 'His Second Chance', reason: '入场期: 近3天ROI均值>40%', confidence: 0.69, timestamp: '2026-09-05T14:26:05Z' },
  { signal_id: '20260905112938_2046008811200349184', signal_type: 'FOLLOW_UP', target_dimension: 'product', target_id: '2046008811200349184', language_code: '西班牙语', script_no: 'LA199', shortplay_name: "The Mafia's Promise", reason: '稳定期: ROI 61% 且波动平缓', confidence: 0.82, timestamp: '2026-09-05T11:29:38Z' },
  { signal_id: '20260904220311_campaign_041', signal_type: 'FOLLOW_UP', target_dimension: 'campaign', target_id: 'campaign_041_mno102', language_code: '英语', script_no: 'LA118', shortplay_name: 'Love After the Storm', reason: '持续盈利Campaign: ROI>40% 已持续7天', confidence: 0.84, timestamp: '2026-09-04T22:03:11Z' },
  { signal_id: '20260904174029_2046440911388762112', signal_type: 'FOLLOW_UP', target_dimension: 'product', target_id: '2046440911388762112', language_code: '马来西亚语', script_no: 'LA056', shortplay_name: "The Billionaire's Trap", reason: '成长期: ROI>88% 且趋势上升24%', confidence: 0.75, timestamp: '2026-09-04T17:40:29Z' },
  { signal_id: '20260904130255_2046772200199847936', signal_type: 'FOLLOW_UP', target_dimension: 'product', target_id: '2046772200199847936', language_code: '泰语', script_no: 'LA092', shortplay_name: 'Reborn to Love You', reason: '入场期: 近3天ROI均值>40%', confidence: 0.72, timestamp: '2026-09-04T13:02:55Z' },
  { signal_id: '20260903214517_campaign_119', signal_type: 'FOLLOW_UP', target_dimension: 'campaign', target_id: 'campaign_119_mno211', language_code: '印尼语', script_no: 'LA134', shortplay_name: 'The Heiress Returns', reason: '成长期Campaign: ROI>40% 持续上升', confidence: 0.79, timestamp: '2026-09-03T21:45:17Z' },
  { signal_id: '20260903180644_2047118822000441856', signal_type: 'FOLLOW_UP', target_dimension: 'product', target_id: '2047118822000441856', language_code: '英语', script_no: 'LA061', shortplay_name: 'Married to My Enemy', reason: '稳定期: ROI 43% 且波动平缓', confidence: 0.73, timestamp: '2026-09-03T18:06:44Z' },
  { signal_id: '20260903143820_2047550033116622848', signal_type: 'FOLLOW_UP', target_dimension: 'product', target_id: '2047550033116622848', language_code: '越南语', script_no: 'LA077', shortplay_name: 'The Runaway Bride', reason: '成长期: ROI>140% 且趋势上升52%', confidence: 0.86, timestamp: '2026-09-03T14:38:20Z' },
  { signal_id: '20260903095107_2047881100223315456', signal_type: 'FOLLOW_UP', target_dimension: 'product', target_id: '2047881100223315456', language_code: '印尼语', script_no: 'LA015', shortplay_name: 'My Cold Husband', reason: '入场期: 近3天ROI均值>40%', confidence: 0.68, timestamp: '2026-09-03T09:51:07Z' },
  { signal_id: '20260902223341_campaign_072', signal_type: 'FOLLOW_UP', target_dimension: 'campaign', target_id: 'campaign_072_mno186', language_code: '西班牙语', script_no: 'LA187', shortplay_name: "The Tycoon's Daughter", reason: '持续盈利Campaign: ROI>40% 已持续7天', confidence: 0.83, timestamp: '2026-09-02T22:33:41Z' },
  { signal_id: '20260902155912_2048220011993387520', signal_type: 'FOLLOW_UP', target_dimension: 'product', target_id: '2048220011993387520', language_code: '泰语', script_no: 'LA028', shortplay_name: 'Love in the Shadows', reason: '成长期: ROI>105% 且趋势上升31%', confidence: 0.78, timestamp: '2026-09-02T15:59:12Z' },
]

const PAGE_SIZE = 20

const decisions = ref<any[]>([...MOCK_SIGNALS])
const filterType = ref('')
const currentPage = ref(1)
const detailVisible = ref(false)
const detailContent = ref('')

const filteredDecisions = computed(() => {
  if (!filterType.value) return decisions.value
  return decisions.value.filter((d) => d.signal_type === filterType.value)
})

const total = computed(() => filteredDecisions.value.length)

const pagedDecisions = computed(() => {
  const start = (currentPage.value - 1) * PAGE_SIZE
  return filteredDecisions.value.slice(start, start + PAGE_SIZE)
})

watch(filterType, () => {
  currentPage.value = 1
})

function refresh() {
  decisions.value = [...MOCK_SIGNALS]
  currentPage.value = 1
  ElMessage.success('已重置为示例数据')
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

.title-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mock-tag {
  color: #909399;
  font-size: 12px;
}

pre {
  background: #f5f7fa;
  padding: 15px;
  border-radius: 4px;
  overflow-x: auto;
}
</style>

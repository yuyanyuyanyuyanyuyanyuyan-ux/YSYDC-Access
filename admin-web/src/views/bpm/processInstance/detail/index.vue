<template>
  <div>
    <!-- 工单/预约信息 -->
    <el-card shadow="never" class="mb-20px">
      <template #header>
        <span class="font-bold">工单/预约信息</span>
      </template>
      <el-descriptions :column="3" border>
        <template v-for="f in detail.display_fields || []" :key="f.field_key">
          <el-descriptions-item v-if="f.input_type !== 'visitors'" :label="f.field_name">
            {{ f.value || '—' }}
          </el-descriptions-item>
          <el-descriptions-item v-else :label="f.field_name">
            {{ (f.value || []).length }} 人
          </el-descriptions-item>
        </template>
        <el-descriptions-item label="审批状态">
          <el-tag :type="statusTagType">{{ statusText }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="申请时间">{{ detail.application_time }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 来访人员详情 -->
    <el-card v-if="visitorField && visitorField.value && visitorField.value.length" shadow="never" class="mb-20px">
      <template #header>
        <span class="font-bold">来访人员（{{ visitorField.value.length }}人）</span>
      </template>
      <el-table :data="visitorField.value" size="small" border>
        <el-table-column prop="name" label="姓名" min-width="100" />
        <el-table-column prop="id_card" label="身份证" min-width="160" />
        <el-table-column prop="phone" label="电话" min-width="130" />
        <el-table-column prop="unit" label="单位" min-width="140" />
      </el-table>
    </el-card>

    <!-- 审批流程图 -->
    <el-card shadow="never" class="mb-20px">
      <template #header>
        <span class="font-bold">审批流程</span>
      </template>
      <div class="flow-box">
        <template v-for="(node, i) in flowNodes" :key="node.id">
          <div class="flow-node" :class="'status-' + node.flow_status">
            <div class="node-name">{{ node.step_name }}</div>
            <div class="node-role">{{ node.required_role }}</div>
            <div class="node-status">{{ flowStatusText(node.flow_status) }}</div>
          </div>
          <div v-if="i < flowNodes.length - 1" class="flow-arrow">→</div>
        </template>
      </div>
    </el-card>

    <!-- 审批历史 -->
    <el-card shadow="never" class="mb-20px">
      <template #header>
        <span class="font-bold">审批历史</span>
      </template>
      <el-timeline v-if="history.length">
        <el-timeline-item
          v-for="(h, i) in history"
          :key="i"
          :timestamp="h.created_at"
          :type="h.action === 'approved' ? 'success' : 'danger'"
        >
          <div class="font-medium">{{ h.step_name }} · {{ h.approver_name }}（{{ h.role }}）</div>
          <div>
            {{ h.action === 'approved' ? '通过' : '驳回' }}<span v-if="h.comment">：{{ h.comment }}</span>
          </div>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-else description="暂无审批记录" />
    </el-card>

    <!-- 审批操作 -->
    <el-card v-if="taskId" shadow="never">
      <template #header>
        <span class="font-bold">审批操作</span>
      </template>
      <el-input v-model="comment" type="textarea" :rows="3" placeholder="审批意见（驳回时必填）" />
      <div class="mt-20px">
        <el-button type="success" @click="handleAction('approved')">通过</el-button>
        <el-button type="danger" @click="handleAction('rejected')">驳回</el-button>
      </div>
    </el-card>
  </div>
</template>

<script lang="ts" setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/config/axios'

defineOptions({ name: 'BpmProcessInstanceDetail' })

const route = useRoute()
const router = useRouter()
const recordId = Number(route.query.id)
const taskId = route.query.taskId ? Number(route.query.taskId) : null

const detail = ref<any>({})
const history = ref<any[]>([])
const flowNodes = ref<any[]>([])
const comment = ref('')

const statusText = computed(() => {
  const m: Record<string, string> = { pending: '待审批', approved: '已通过', rejected: '已驳回' }
  return m[detail.value.approval_status] || detail.value.approval_status || ''
})
const statusTagType = computed<'success' | 'warning' | 'danger' | 'info'>(() => {
  const m: Record<string, 'success' | 'warning' | 'danger' | 'info'> = { pending: 'warning', approved: 'success', rejected: 'danger' }
  return m[detail.value.approval_status] || 'info'
})
const visitorField = computed(() => {
  return (detail.value.display_fields || []).find((f: any) => f.input_type === 'visitors') || null
})

const flowStatusText = (s: string) => {
  const m: Record<string, string> = {
    completed: '已完成',
    current: '审批中',
    pending: '待审批',
    rejected: '已驳回'
  }
  return m[s] || s
}

const load = async () => {
  try {
    const [d, f] = await Promise.all([
      request.get({ url: `/api/approval-detail/${recordId}` }),
      request.get({ url: `/api/work-orders/${recordId}/flow` })
    ])
    detail.value = d.detail || {}
    history.value = d.history || []
    flowNodes.value = (f.nodes || []).slice().sort((a: any, b: any) => (a.step_order ?? 0) - (b.step_order ?? 0))
  } catch (e) {
    /* 错误提示已由 axios 拦截器统一处理 */
  }
}

const handleAction = async (action: string) => {
  if (action === 'rejected' && !comment.value.trim()) {
    ElMessage.warning('驳回时必须填写审批意见')
    return
  }
  try {
    await ElMessageBox.confirm(`确认${action === 'approved' ? '通过' : '驳回'}该审批？`, '提示', {
      type: 'warning'
    })
  } catch (e) {
    return
  }
  try {
    await request.post({
      url: `/api/approval-task/${taskId}/action`,
      data: { action, comment: comment.value }
    })
    ElMessage.success('审批成功')
    router.push('/bpm/todo')
  } catch (e) {
    /* 错误提示已由 axios 拦截器统一处理 */
  }
}

onMounted(load)
</script>

<style lang="scss" scoped>
.flow-box {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
}
.flow-node {
  padding: 12px 16px;
  border-radius: 6px;
  border: 1px solid #dcdfe6;
  text-align: center;
  min-width: 120px;
}
.flow-node.status-completed {
  border-color: #67c23a;
  background: #f0f9eb;
}
.flow-node.status-current {
  border-color: #409eff;
  background: #ecf5ff;
}
.flow-node.status-pending {
  border-color: #e6a23c;
  background: #fdf6ec;
}
.flow-node.status-rejected {
  border-color: #f56c6c;
  background: #fef0f0;
}
.flow-arrow {
  margin: 0 12px;
  font-size: 20px;
  color: #909399;
}
.node-name {
  font-weight: 600;
}
.node-role {
  font-size: 12px;
  color: #909399;
}
.node-status {
  font-size: 12px;
  margin-top: 4px;
}
</style>

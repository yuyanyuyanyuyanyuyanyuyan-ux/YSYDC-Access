<template>
  <el-card shadow="never">
    <template #header>
      <div class="flex items-center justify-between">
        <span class="font-bold">工单列表</span>
        <div class="flex items-center gap-10px">
          <el-input
            v-model="query.company"
            placeholder="按单位搜索"
            clearable
            class="w-200px"
            @keyup.enter="load"
            @clear="load"
          />
          <el-select v-model="query.status" placeholder="审批状态" clearable class="w-140px" @change="load">
            <el-option label="待审批" value="pending" />
            <el-option label="已通过" value="approved" />
            <el-option label="已驳回" value="rejected" />
          </el-select>
          <el-button type="primary" @click="load">查询</el-button>
        </div>
      </div>
    </template>
    <el-table v-loading="loading" :data="list" stripe>
      <el-table-column prop="company" label="来访单位" min-width="140" show-overflow-tooltip />
      <el-table-column prop="entry_time" label="进入时间" min-width="130" />
      <el-table-column prop="reason" label="进出原因" min-width="100" />
      <el-table-column prop="area" label="活动区域" min-width="110" />
      <el-table-column prop="accompanying_person" label="陪同人员" min-width="100" />
      <el-table-column label="审批状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.approval_status)">
            {{ statusText(row.approval_status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="current_step_name" label="当前节点" min-width="130" />
      <el-table-column prop="application_time" label="申请时间" min-width="160" />
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link @click="goDetail(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script lang="ts" setup>
import request from '@/config/axios'

defineOptions({ name: 'BpmWorkOrders' })

const { push } = useRouter()
const list = ref<any[]>([])
const loading = ref(false)
const query = reactive({ status: '', company: '' })

const statusText = (s: string) => {
  const m: Record<string, string> = { pending: '待审批', approved: '已通过', rejected: '已驳回' }
  return m[s] || s
}
const statusTagType = (s: string): 'success' | 'warning' | 'danger' | 'info' => {
  const m: Record<string, 'success' | 'warning' | 'danger' | 'info'> = { pending: 'warning', approved: 'success', rejected: 'danger' }
  return m[s] || 'info'
}

const load = async () => {
  loading.value = true
  try {
    const params: Record<string, any> = {}
    if (query.status) params.status = query.status
    if (query.company) params.company = query.company
    const res = await request.get({ url: '/api/work-orders', params })
    list.value = res.list || []
  } catch (e) {
    /* 错误提示已由 axios 拦截器统一处理 */
  } finally {
    loading.value = false
  }
}

const goDetail = (row: any) => {
  push({ path: '/bpm/process-instance/detail', query: { id: row.approval_record_id } })
}

onMounted(load)
</script>

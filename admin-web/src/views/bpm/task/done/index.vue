<template>
  <el-card shadow="never">
    <template #header>
      <span class="font-bold">已办任务</span>
    </template>
    <el-table v-loading="loading" :data="list" stripe>
      <el-table-column prop="name" label="姓名" min-width="90" />
      <el-table-column prop="phone" label="手机号" min-width="120" />
      <el-table-column prop="company" label="公司/单位" min-width="140" show-overflow-tooltip />
      <el-table-column prop="score" label="考试成绩" width="90" />
      <el-table-column prop="step_name" label="审批节点" min-width="130" />
      <el-table-column label="处理结果" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'approved' ? 'success' : 'danger'">
            {{ row.status === 'approved' ? '已通过' : '已驳回' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="comment" label="审批意见" min-width="140" show-overflow-tooltip />
      <el-table-column prop="approved_at" label="处理时间" min-width="160" />
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

defineOptions({ name: 'BpmDoneTask' })

const { push } = useRouter()
const list = ref<any[]>([])
const loading = ref(false)

const load = async () => {
  loading.value = true
  try {
    const res = await request.get({ url: '/api/tasks/completed' })
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

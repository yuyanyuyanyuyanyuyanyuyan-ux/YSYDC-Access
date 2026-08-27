<template>
  <el-card shadow="never">
    <template #header>
      <span class="font-bold">待办任务</span>
    </template>
    <el-table v-loading="loading" :data="list" stripe>
      <el-table-column prop="name" label="姓名" min-width="90" />
      <el-table-column prop="phone" label="手机号" min-width="120" />
      <el-table-column prop="company" label="公司/单位" min-width="140" show-overflow-tooltip />
      <el-table-column prop="identity_type" label="身份类型" min-width="90" />
      <el-table-column prop="visit_purpose" label="来访目的" min-width="140" show-overflow-tooltip />
      <el-table-column prop="score" label="考试成绩" width="90" />
      <el-table-column prop="step_name" label="当前审批节点" min-width="130" />
      <el-table-column prop="created_at" label="提交时间" min-width="160" />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link @click="goDetail(row, true)">办理</el-button>
          <el-button type="primary" link @click="goDetail(row, false)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script lang="ts" setup>
import request from '@/config/axios'

defineOptions({ name: 'BpmTodoTask' })

const { push } = useRouter()
const list = ref<any[]>([])
const loading = ref(false)

const load = async () => {
  loading.value = true
  try {
    const res = await request.get({ url: '/api/tasks/pending' })
    list.value = res.list || []
  } catch (e) {
    /* 错误提示已由 axios 拦截器统一处理 */
  } finally {
    loading.value = false
  }
}

const goDetail = (row: any, withTask: boolean) => {
  const query: Record<string, any> = { id: row.approval_record_id }
  if (withTask && row.task_id) {
    query.taskId = row.task_id
  }
  push({ path: '/bpm/process-instance/detail', query })
}

onMounted(load)
</script>

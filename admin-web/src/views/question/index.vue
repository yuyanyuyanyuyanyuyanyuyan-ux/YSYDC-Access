<template>
  <el-card shadow="never">
    <template #header>
      <div class="flex items-center justify-between">
        <span class="font-bold">题库管理</span>
        <el-button type="primary" @click="openDialog()">新增题目</el-button>
      </div>
    </template>

    <el-table v-loading="loading" :data="list" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="question" label="题目" min-width="200" show-overflow-tooltip />
      <el-table-column prop="option_a" label="选项A" min-width="100" show-overflow-tooltip />
      <el-table-column prop="option_b" label="选项B" min-width="100" show-overflow-tooltip />
      <el-table-column prop="option_c" label="选项C" min-width="100" show-overflow-tooltip />
      <el-table-column prop="option_d" label="选项D" min-width="100" show-overflow-tooltip />
      <el-table-column prop="score" label="分值" width="70" />
      <el-table-column prop="correct_answer" label="答案" width="70" />
      <el-table-column label="启用" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link @click="openDialog(row)">编辑</el-button>
          <el-button type="danger" link @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑题目' : '新增题目'" width="640px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="题目">
          <el-input v-model="form.question" type="textarea" :rows="2" placeholder="题目内容" />
        </el-form-item>
        <el-form-item label="选项A">
          <el-input v-model="form.option_a" placeholder="选项A" />
        </el-form-item>
        <el-form-item label="选项B">
          <el-input v-model="form.option_b" placeholder="选项B" />
        </el-form-item>
        <el-form-item label="选项C">
          <el-input v-model="form.option_c" placeholder="选项C" />
        </el-form-item>
        <el-form-item label="选项D">
          <el-input v-model="form.option_d" placeholder="选项D" />
        </el-form-item>
        <el-form-item label="分值">
          <el-input-number v-model="form.score" :min="1" :max="100" />
        </el-form-item>
        <el-form-item label="正确答案">
          <el-select v-model="form.correct_answer" class="w-full">
            <el-option label="A" value="A" />
            <el-option label="B" value="B" />
            <el-option label="C" value="C" />
            <el-option label="D" value="D" />
          </el-select>
        </el-form-item>
        <el-form-item label="是否启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script lang="ts" setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/config/axios'

defineOptions({ name: 'QuestionBank' })

const list = ref<any[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const form = reactive({
  id: null as number | null,
  question: '',
  option_a: '',
  option_b: '',
  option_c: '',
  option_d: '',
  score: 10,
  correct_answer: 'A',
  is_active: true
})

const load = async () => {
  loading.value = true
  try {
    const res = await request.get({ url: '/api/admin/questions' })
    list.value = res.list || []
  } catch (e) {
    /* 错误提示已由 axios 拦截器统一处理 */
  } finally {
    loading.value = false
  }
}

const openDialog = (row?: any) => {
  if (row) {
    form.id = row.id
    form.question = row.question
    form.option_a = row.option_a || ''
    form.option_b = row.option_b || ''
    form.option_c = row.option_c || ''
    form.option_d = row.option_d || ''
    form.score = row.score || 10
    form.correct_answer = row.correct_answer || 'A'
    form.is_active = !!row.is_active
  } else {
    form.id = null
    form.question = ''
    form.option_a = ''
    form.option_b = ''
    form.option_c = ''
    form.option_d = ''
    form.score = 10
    form.correct_answer = 'A'
    form.is_active = true
  }
  dialogVisible.value = true
}

const save = async () => {
  if (!form.question.trim()) {
    ElMessage.warning('请输入题目内容')
    return
  }
  try {
    if (form.id) {
      await request.put({
        url: `/api/admin/questions/${form.id}`,
        data: { ...form }
      })
    } else {
      await request.post({ url: '/api/admin/questions', data: { ...form } })
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    load()
  } catch (e) {
    /* 错误提示已由 axios 拦截器统一处理 */
  }
}

const remove = async (row: any) => {
  try {
    await ElMessageBox.confirm(`确认删除题目「${row.question}」？`, '提示', { type: 'warning' })
  } catch (e) {
    return
  }
  try {
    await request.delete({ url: `/api/admin/questions/${row.id}` })
    ElMessage.success('删除成功')
    load()
  } catch (e) {
    /* 错误提示已由 axios 拦截器统一处理 */
  }
}

onMounted(load)
</script>

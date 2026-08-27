<template>
  <el-card shadow="never">
    <template #header>
      <div class="flex items-center justify-between">
        <span class="font-bold">业务部成员管理</span>
        <el-button type="primary" @click="openDialog()">新建成员</el-button>
      </div>
    </template>

    <el-table v-loading="loading" :data="list" stripe>
      <el-table-column prop="username" label="账号" min-width="120" />
      <el-table-column prop="real_name" label="姓名" min-width="100" />
      <el-table-column prop="phone" label="手机号" min-width="130" />
      <el-table-column prop="created_at" label="创建时间" min-width="160" />
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link @click="openDialog(row)">编辑</el-button>
          <el-button type="danger" link @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑成员' : '新建成员'" width="480px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="账号">
          <el-input v-model="form.username" :disabled="!!form.id" placeholder="账号" />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="form.real_name" placeholder="姓名" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="form.phone" placeholder="手机号" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" :placeholder="form.id ? '留空则不修改密码' : '密码'" />
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

defineOptions({ name: 'BusinessMember' })

const list = ref<any[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const form = reactive({ id: null as number | null, username: '', real_name: '', phone: '', password: '' })

const load = async () => {
  loading.value = true
  try {
    const res = await request.get({ url: '/api/business-members' })
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
    form.username = row.username
    form.real_name = row.real_name || ''
    form.phone = row.phone || ''
    form.password = ''
  } else {
    form.id = null
    form.username = ''
    form.real_name = ''
    form.phone = ''
    form.password = ''
  }
  dialogVisible.value = true
}

const save = async () => {
  if (!form.username) {
    ElMessage.warning('请输入账号')
    return
  }
  if (!form.id && !form.password) {
    ElMessage.warning('请输入密码')
    return
  }
  try {
    if (form.id) {
      await request.put({
        url: `/api/business-members/${form.id}`,
        data: { real_name: form.real_name, phone: form.phone, password: form.password }
      })
    } else {
      await request.post({
        url: '/api/business-members',
        data: { username: form.username, password: form.password, real_name: form.real_name, phone: form.phone }
      })
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
    await ElMessageBox.confirm(`确认删除成员「${row.username}」？`, '提示', { type: 'warning' })
  } catch (e) {
    return
  }
  try {
    await request.delete({ url: `/api/business-members/${row.id}` })
    ElMessage.success('删除成功')
    load()
  } catch (e) {
    /* 错误提示已由 axios 拦截器统一处理 */
  }
}

onMounted(load)
</script>

<template>
  <el-card shadow="never">
    <template #header>
      <div class="flex items-center justify-between">
        <span class="font-bold">自定义工单内容</span>
        <div class="flex items-center gap-10px">
          <el-button @click="resetDefault">恢复默认</el-button>
          <el-button type="primary" @click="addField">新增条目</el-button>
        </div>
      </div>
    </template>

    <el-alert
      class="mb-12px"
      type="info"
      :closable="false"
      show-icon
      title="下面是当前工单结构。可新增/编辑/删除条目，修改完成后点击底部「保存」，业务部填写工单时即按此结构。"
    />

    <el-table v-loading="loading" :data="fields" stripe>
      <el-table-column prop="sort_order" label="排序" width="70" />
      <el-table-column prop="field_name" label="条款名称" min-width="140" show-overflow-tooltip />
      <el-table-column label="输入方式" width="130">
        <template #default="{ row }">
          <el-tag>{{ inputTypeText(row.input_type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="选项" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.input_type === 'select'">{{ (row.options || []).join('、') || '—' }}</span>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="必填" width="70">
        <template #default="{ row }">
          <el-tag :type="row.required ? 'danger' : 'info'">{{ row.required ? '是' : '否' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="默认" width="70">
        <template #default="{ row }">
          <el-tag v-if="row.is_default" type="success">默认</el-tag>
          <el-tag v-else type="warning">自定义</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row, $index }">
          <el-button type="primary" link @click="editField(row)">编辑</el-button>
          <el-button
            v-if="row.field_key !== 'visitors'"
            type="danger"
            link
            @click="removeField($index)"
          >
            删除
          </el-button>
          <el-tooltip v-else content="来访人员为必留字段，不可删除" placement="top">
            <span class="text-12px text-gray-400">不可删</span>
          </el-tooltip>
        </template>
      </el-table-column>
    </el-table>

    <div class="mt-20px flex justify-end">
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </div>

    <el-dialog v-model="dialogVisible" :title="editingIndex === null ? '新增条目' : '编辑条目'" width="560px">
      <el-form :model="editForm" label-width="90px">
        <el-form-item label="条款名称">
          <el-input v-model="editForm.field_name" placeholder="如：施工人数、来访事由" />
        </el-form-item>

        <el-form-item label="输入方式">
          <el-select v-model="editForm.input_type" class="w-full" :disabled="editForm.field_key === 'visitors'">
            <el-option label="单行文本（键盘输入）" value="text" />
            <el-option label="多行文本（键盘输入）" value="textarea" />
            <el-option label="选择框（下拉选择）" value="select" />
            <el-option label="日期（选择框）" value="date" />
            <el-option label="时间（选择框）" value="time" />
            <el-option label="日期时间（选择框）" value="datetime" />
            <el-option v-if="editForm.field_key === 'visitors'" label="来访人员（多人列表，不可改）" value="visitors" />
          </el-select>
        </el-form-item>

        <el-form-item v-if="editForm.input_type === 'select'" label="选择项">
          <el-input
            v-model="optionsText"
            type="textarea"
            :rows="3"
            placeholder="每行一个选项，如：&#10;设备维护&#10;施工&#10;参观考察"
          />
          <div class="text-12px text-gray-400">每行一个选项。</div>
        </el-form-item>

        <el-form-item label="是否必填">
          <el-switch v-model="editForm.required" />
        </el-form-item>

        <el-form-item label="排序">
          <el-input-number v-model="editForm.sort_order" :min="0" :max="999" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmEdit">确定</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script lang="ts" setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/config/axios'

defineOptions({ name: 'WorkOrderCustomField' })

const fields = ref<any[]>([])
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const optionsText = ref('')
const editingIndex = ref<number | null>(null)

const editForm = reactive({
  field_key: '',
  field_name: '',
  input_type: 'text',
  required: false,
  sort_order: 0
})

const inputTypeText = (t: string) => {
  const m: Record<string, string> = {
    text: '单行文本',
    textarea: '多行文本',
    select: '选择框',
    date: '日期',
    time: '时间',
    datetime: '日期时间',
    visitors: '来访人员'
  }
  return m[t] || t
}

const load = async () => {
  loading.value = true
  try {
    const res = await request.get({ url: '/api/admin/work-order-fields' })
    fields.value = res.list || []
  } catch (e) {
    /* 错误提示已由 axios 拦截器统一处理 */
  } finally {
    loading.value = false
  }
}

const addField = () => {
  editingIndex.value = null
  Object.assign(editForm, {
    field_key: '',
    field_name: '',
    input_type: 'text',
    required: false,
    sort_order: fields.value.length + 1
  })
  optionsText.value = ''
  dialogVisible.value = true
}

const editField = (row: any) => {
  const idx = fields.value.findIndex((f) => f.field_key === row.field_key)
  editingIndex.value = idx
  Object.assign(editForm, {
    field_key: row.field_key,
    field_name: row.field_name,
    input_type: row.input_type,
    required: !!row.required,
    sort_order: row.sort_order ?? idx + 1
  })
  optionsText.value = (row.options || []).join('\n')
  dialogVisible.value = true
}

const removeField = (index: number) => {
  fields.value.splice(index, 1)
}

const confirmEdit = () => {
  if (!editForm.field_name.trim()) {
    ElMessage.warning('请输入条款名称')
    return
  }
  const options = editForm.input_type === 'select'
    ? optionsText.value.split('\n').map((s) => s.trim()).filter(Boolean)
    : []
  if (editForm.input_type === 'select' && options.length === 0) {
    ElMessage.warning('选择框类型至少要填一个选项')
    return
  }
  const item = {
    field_key: editForm.field_key,
    field_name: editForm.field_name.trim(),
    input_type: editForm.input_type,
    options,
    required: editForm.required,
    sort_order: editForm.sort_order
  }
  if (editingIndex.value === null) {
    fields.value.push(item)
  } else {
    fields.value[editingIndex.value] = item
  }
  dialogVisible.value = false
}

const save = async () => {
  if (fields.value.length === 0) {
    ElMessage.warning('工单结构不能为空')
    return
  }
  saving.value = true
  try {
    await request.post({
      url: '/api/admin/work-order-fields/save',
      data: { fields: fields.value }
    })
    ElMessage.success('保存成功，业务部工单将按新结构填写')
    await load()
  } catch (e) {
    /* 错误提示已由 axios 拦截器统一处理 */
  } finally {
    saving.value = false
  }
}

const resetDefault = async () => {
  try {
    await ElMessageBox.confirm('确认恢复为默认工单结构？当前自定义条目将被清除。', '提示', {
      type: 'warning'
    })
  } catch (e) {
    return
  }
  try {
    await request.post({ url: '/api/admin/work-order-fields/reset' })
    ElMessage.success('已恢复默认结构')
    await load()
  } catch (e) {
    /* 错误提示已由 axios 拦截器统一处理 */
  }
}

onMounted(load)
</script>

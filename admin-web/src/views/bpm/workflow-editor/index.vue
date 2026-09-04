<template>
  <div class="flex flex-col h-full">
    <!-- 顶部工具栏 -->
    <el-card shadow="never" class="mb-12px">
      <div class="flex items-center justify-between flex-wrap gap-10px">
        <div class="flex items-center gap-10px">
          <span class="font-bold">审批流程配置</span>
          <el-tag type="info" size="small">按访问原因分配审批流，单链：每节点一个上级、一个下级</el-tag>
        </div>
        <div class="flex items-center gap-10px flex-wrap">
          <el-select v-model="currentFlowId" placeholder="选择访问事务" class="w-200px" @change="onFlowChange">
            <el-option v-for="f in flows" :key="f.id" :label="`${f.flow_no} - ${f.reason}`" :value="f.id" />
          </el-select>
          <el-button @click="openAddReason">新增访问事务</el-button>
          <el-select v-model="newAdminId" placeholder="选择管理员" class="w-200px" clearable>
            <el-option v-for="a in admins" :key="a.id" :label="`${a.real_name}（${a.role}）`" :value="a.id" />
          </el-select>
          <el-button type="primary" :disabled="!newAdminId" @click="addNode">添加审批节点</el-button>
          <el-button @click="load">刷新</el-button>
        </div>
      </div>
    </el-card>

    <!-- 新增访问事务弹窗 -->
    <el-dialog v-model="reasonDialogVisible" title="新增访问事务" width="420px">
      <el-input v-model="newReason" placeholder="访问原因，如：设备检修、上级视察" @keyup.enter="submitReason" />
      <template #footer>
        <el-button @click="reasonDialogVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!newReason.trim()" @click="submitReason">确定</el-button>
      </template>
    </el-dialog>

    <!-- 画布 -->
    <div
      ref="canvasRef"
      class="canvas"
      @mousemove="onCanvasMouseMove"
      @mouseup="onCanvasMouseUp"
    >
      <!-- 连线（SVG 层） -->
      <svg class="canvas-svg">
        <defs>
          <marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
            <path d="M0,0 L0,6 L9,3 z" fill="#909399" />
          </marker>
        </defs>
        <g v-for="t in transitions" :key="t.id">
          <line
            :x1="t.x1"
            :y1="t.y1"
            :x2="t.x2"
            :y2="t.y2"
            stroke="#909399"
            stroke-width="2"
            marker-end="url(#arrow)"
            class="line-click"
            @click="removeTransition(t)"
          />
        </g>
        <!-- 拖拽连线中的临时线 -->
        <line
          v-if="dragLine"
          :x1="dragLine.x1"
          :y1="dragLine.y1"
          :x2="dragLine.x2"
          :y2="dragLine.y2"
          stroke="#409eff"
          stroke-width="2"
          stroke-dasharray="5,5"
          marker-end="url(#arrow)"
        />
      </svg>

      <!-- 节点 -->
      <div
        v-for="n in nodes"
        :key="n.id"
        class="node"
        :style="{ left: n.node_x + 'px', top: n.node_y + 'px' }"
        @mousedown="onNodeMouseDown($event, n)"
      >
        <div class="node-header">
          <span class="node-name">{{ n.step_name || (n.approver_name || '未命名') }}</span>
          <el-icon class="node-del" @mousedown.stop @click="removeNode(n)"><Close /></el-icon>
        </div>
        <div class="node-role">{{ n.approver_name || '未绑定' }}<span v-if="n.approver_role"> · {{ n.approver_role }}</span></div>
        <!-- 连接点：拖出连线 -->
        <div class="port port-out" title="从此拖出连线" @mousedown.stop="onPortMouseDown($event, n)"></div>
      </div>

      <el-empty v-if="!nodes.length" description="暂无审批节点，请在上方选择管理员添加" class="canvas-empty" />
    </div>

    <div class="mt-8px text-12px text-gray-400">
      提示：拖动节点可调整位置；按住节点右下角的圆点拖到另一个节点即可建立连线；点击连线可删除；点击节点右上角 × 可删除节点。
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { Close } from '@element-plus/icons-vue'
import request from '@/config/axios'

defineOptions({ name: 'WorkflowEditor' })

const canvasRef = ref<HTMLElement>()
const nodes = ref<any[]>([])
const transitions = ref<any[]>([])
const admins = ref<any[]>([])
const flows = ref<any[]>([])
const currentFlowId = ref<number | null>(null)
const newAdminId = ref<number | null>(null)
const reasonDialogVisible = ref(false)
const newReason = ref('')

// 拖拽状态
const dragNode = ref<any>(null) // 正在拖动的节点
const dragOffset = ref({ x: 0, y: 0 })
const dragLine = ref<any>(null) // 正在拖拽的临时连线
const dragFromNode = ref<any>(null)

const NODE_W = 180
const NODE_H = 70

const nodeCenter = (n: any) => ({ x: (n.node_x || 0) + NODE_W / 2, y: (n.node_y || 0) + NODE_H / 2 })

const buildTransitionsWithPos = () => {
  transitions.value = transitions.value.map((t) => {
    const from = nodes.value.find((n) => n.id === t.from_step_id)
    const to = nodes.value.find((n) => n.id === t.to_step_id)
    const f = from ? nodeCenter(from) : { x: 0, y: 0 }
    const g = to ? nodeCenter(to) : { x: 0, y: 0 }
    return { ...t, x1: f.x, y1: f.y, x2: g.x, y2: g.y }
  })
}

const loadFlows = async () => {
  const f = await request.get({ url: '/api/workflow/flows' })
  flows.value = f.list || []
  if (!currentFlowId.value && flows.value.length) {
    currentFlowId.value = flows.value[0].id
  }
}

const load = async () => {
  try {
    await loadFlows()
    const a = await request.get({ url: '/api/workflow/admins' })
    admins.value = a.list || []
    if (currentFlowId.value) {
      const [n, t] = await Promise.all([
        request.get({ url: '/api/workflow/nodes', params: { flow_id: currentFlowId.value } }),
        request.get({ url: '/api/workflow/transitions', params: { flow_id: currentFlowId.value } })
      ])
      nodes.value = (n.list || []).filter((x: any) => x.approver_type === 'user')
      transitions.value = t.list || []
    } else {
      nodes.value = []
      transitions.value = []
    }
    buildTransitionsWithPos()
  } catch (e) {
    /* 错误提示已由 axios 拦截器统一处理 */
  }
}

const onFlowChange = () => {
  load()
}

const openAddReason = () => {
  newReason.value = ''
  reasonDialogVisible.value = true
}

const submitReason = async () => {
  const reason = newReason.value.trim()
  if (!reason) return
  try {
    const res = await request.post({ url: '/api/workflow/flows', data: { reason } })
    ElMessage.success('访问事务已创建，审批流已同步生成')
    reasonDialogVisible.value = false
    currentFlowId.value = res.flow_id
    await load()
  } catch (e) {
    /* 错误提示已由 axios 拦截器统一处理 */
  }
}

// ---- 节点增删 ----
const addNode = async () => {
  try {
    await request.post({
      url: '/api/workflow/nodes',
      data: { approver_id: newAdminId.value, node_x: 60, node_y: 60, flow_id: currentFlowId.value }
    })
    ElMessage.success('节点已添加')
    newAdminId.value = null
    await load()
  } catch (e) {
    /* 错误提示已由 axios 拦截器统一处理 */
  }
}

const removeNode = async (n: any) => {
  try {
    await ElMessageBox.confirm(`确认删除审批节点「${n.step_name || n.approver_name}」？其相关连线将一并删除。`, '提示', { type: 'warning' })
  } catch (e) {
    return
  }
  try {
    await request.delete({ url: `/api/workflow/nodes/${n.id}` })
    ElMessage.success('已删除')
    await load()
  } catch (e) {
    /* 错误提示已由 axios 拦截器统一处理 */
  }
}

// ---- 节点拖动 ----
const onNodeMouseDown = (e: MouseEvent, n: any) => {
  const rect = canvasRef.value!.getBoundingClientRect()
  dragNode.value = n
  // offset = 鼠标相对画布的位置 - 节点相对画布的位置（两者同基准）
  dragOffset.value = {
    x: (e.clientX - rect.left) - (n.node_x || 0),
    y: (e.clientY - rect.top) - (n.node_y || 0)
  }
}

const onCanvasMouseMove = (e: MouseEvent) => {
  if (dragNode.value) {
    const rect = canvasRef.value!.getBoundingClientRect()
    const nx = Math.max(0, e.clientX - rect.left - dragOffset.value.x)
    const ny = Math.max(0, e.clientY - rect.top - dragOffset.value.y)
    dragNode.value.node_x = nx
    dragNode.value.node_y = ny
    buildTransitionsWithPos()
  }
  if (dragLine.value) {
    const rect = canvasRef.value!.getBoundingClientRect()
    dragLine.value.x2 = e.clientX - rect.left
    dragLine.value.y2 = e.clientY - rect.top
  }
}

const onCanvasMouseUp = async (e: MouseEvent) => {
  // 结束节点拖动 → 保存位置
  if (dragNode.value) {
    const n = dragNode.value
    dragNode.value = null
    try {
      await request.put({ url: `/api/workflow/nodes/${n.id}`, data: { node_x: Math.round(n.node_x), node_y: Math.round(n.node_y) } })
    } catch (err) {
      /* 忽略保存失败 */
    }
    return
  }
  // 结束连线拖动 → 若落在某节点上则建立连线
  if (dragLine.value) {
    const target = hitTestNode(e)
    const from = dragFromNode.value
    dragLine.value = null
    dragFromNode.value = null
    if (target && target.id !== from.id) {
      try {
        await request.post({
          url: '/api/workflow/transitions',
          data: { from_step_id: from.id, to_step_id: target.id, flow_id: currentFlowId.value }
        })
        ElMessage.success('连线已建立')
      } catch (err) {
        /* 错误提示已由 axios 拦截器统一处理 */
      }
    }
    await load()
  }
}

const hitTestNode = (e: MouseEvent): any | null => {
  const rect = canvasRef.value!.getBoundingClientRect()
  const x = e.clientX - rect.left
  const y = e.clientY - rect.top
  return nodes.value.find((n) => x >= n.node_x && x <= n.node_x + NODE_W && y >= n.node_y && y <= n.node_y + NODE_H) || null
}

// ---- 连线拖拽 ----
const onPortMouseDown = (e: MouseEvent, n: any) => {
  const rect = canvasRef.value!.getBoundingClientRect()
  const c = nodeCenter(n)
  dragFromNode.value = n
  dragLine.value = { x1: c.x, y1: c.y, x2: e.clientX - rect.left, y2: e.clientY - rect.top }
}

const removeTransition = async (t: any) => {
  try {
    await ElMessageBox.confirm('确认删除这条连线？', '提示', { type: 'warning' })
  } catch (e) {
    return
  }
  try {
    await request.delete({ url: `/api/workflow/transitions/${t.id}` })
    ElMessage.success('连线已删除')
    await load()
  } catch (e) {
    /* 错误提示已由 axios 拦截器统一处理 */
  }
}

onMounted(load)
</script>

<style lang="scss" scoped>
.canvas {
  position: relative;
  flex: 1;
  min-height: 480px;
  background: #fafbfc;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  overflow: hidden;
  user-select: none;
}
.canvas-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.line-click {
  pointer-events: stroke;
  cursor: pointer;
}
.node {
  position: absolute;
  width: 180px;
  min-height: 70px;
  background: #fff;
  border: 1px solid #c6cbd4;
  border-radius: 6px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
  cursor: grab;
  padding: 10px 12px;
}
.node-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  font-size: 14px;
}
.node-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.node-del {
  cursor: pointer;
  color: #f56c6c;
  font-size: 14px;
}
.node-role {
  margin-top: 6px;
  font-size: 12px;
  color: #909399;
}
.port {
  position: absolute;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #409eff;
  border: 2px solid #fff;
  cursor: crosshair;
}
.port-out {
  right: -7px;
  top: 50%;
  transform: translateY(-50%);
}
.canvas-empty {
  position: absolute;
  inset: 0;
  margin: auto;
}
</style>

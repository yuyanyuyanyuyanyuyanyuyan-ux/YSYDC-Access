const { BASE_URL } = require('../../config')

// 固定列 key：这些字段的值直接写入 work_orders 对应列，其余进 custom_fields
const FIXED_KEYS = ['company', 'visitors', 'entry_time', 'exit_time', 'reason', 'area', 'contact_name', 'contact_phone', 'accompanying_person']

Page({
  data: {
    fields: [],          // 字段定义 [{field_key, field_name, input_type, options, required, sort_order}]
    formValues: {},      // { field_key: value }
    selectIndex: {},     // { field_key: index } 选择框当前索引
    dtDate: {},          // datetime 类型的日期部分
    dtTime: {},          // datetime 类型的时间部分
    visitors: []         // visitors 类型（来访人员）多人列表
  },

  onLoad() {
    this.loadFields()
  },

  loadFields() {
    const token = wx.getStorageSync('business_token')
    if (!token) return
    wx.request({
      url: BASE_URL + '/api/work-order-fields/active',
      method: 'GET',
      header: { 'Authorization': 'Bearer ' + token },
      success: (res) => {
        if (res.data.success) {
          this.setData({ fields: res.data.fields || [] })
        }
      }
    })
  },

  // ---- 通用输入 ----
  onTextInput(e) {
    const key = e.currentTarget.dataset.key
    this.setData({ [`formValues.${key}`]: e.detail.value })
  },

  // ---- 选择框 ----
  onSelectChange(e) {
    const key = e.currentTarget.dataset.key
    const idx = Number(e.detail.value)
    const f = this.data.fields.find((x) => x.field_key === key)
    const range = f ? (f.options || []) : []
    this.setData({
      [`selectIndex.${key}`]: idx,
      [`formValues.${key}`]: range[idx] ?? ''
    })
  },

  // ---- 日期/时间 ----
  onDateChange(e) {
    const key = e.currentTarget.dataset.key
    this.setData({ [`formValues.${key}`]: e.detail.value })
  },

  onTimeChange(e) {
    const key = e.currentTarget.dataset.key
    this.setData({ [`formValues.${key}`]: e.detail.value })
  },

  // ---- 日期时间（date+time 组合） ----
  onDateTimeChange(e) {
    const key = e.currentTarget.dataset.key
    const part = e.currentTarget.dataset.part
    const map = part === 'date' ? 'dtDate' : 'dtTime'
    this.setData({ [`${map}.${key}`]: e.detail.value })
  },

  // ---- 来访人员（visitors 类型） ----
  addVisitor() {
    this.setData({
      visitors: [...this.data.visitors, { name: '', id_card: '', phone: '', unit: '' }]
    })
  },

  removeVisitor(e) {
    const idx = Number(e.currentTarget.dataset.index)
    this.setData({ visitors: this.data.visitors.filter((_, i) => i !== idx) })
  },

  onVisitorInput(e) {
    const idx = Number(e.currentTarget.dataset.index)
    const field = e.currentTarget.dataset.field
    this.setData({ [`visitors[${idx}].${field}`]: e.detail.value })
  },

  // ---- 取值 ----
  getValue(f) {
    if (f.input_type === 'datetime') {
      const d = this.data.dtDate[f.field_key] || ''
      const t = this.data.dtTime[f.field_key] || ''
      return (d + ' ' + t).trim()
    }
    if (f.input_type === 'visitors') {
      return this.data.visitors
    }
    return this.data.formValues[f.field_key]
  },

  buildPayload(isDraft) {
    const payload = { is_draft: isDraft }
    const custom_fields = {}
    this.data.fields.forEach((f) => {
      let val = this.getValue(f)
      if (FIXED_KEYS.includes(f.field_key)) {
        payload[f.field_key] = val || ''
      } else {
        if (val !== undefined && val !== null && String(val).trim() !== '') {
          custom_fields[f.field_key] = val
        }
      }
    })
    payload.custom_fields = custom_fields
    return payload
  },

  // ---- 提交 ----
  submit() {
    // 必填校验
    for (const f of this.data.fields) {
      if (!f.required) continue
      const val = this.getValue(f)
      const empty = val === undefined || val === null || String(val).trim() === ''
        || (Array.isArray(val) && val.length === 0)
      if (empty) {
        wx.showToast({ title: `请填写「${f.field_name}」`, icon: 'none' })
        return
      }
    }
    // 来访人员：每人姓名、身份证必填
    const visitors = this.data.visitors
    if (visitors.length === 0) {
      wx.showToast({ title: '请至少添加一位来访人员', icon: 'none' })
      return
    }
    for (let i = 0; i < visitors.length; i++) {
      const v = visitors[i]
      if (!v.name || !String(v.name).trim()) {
        wx.showToast({ title: `请填写第${i + 1}位来访人员的姓名`, icon: 'none' })
        return
      }
      if (!v.id_card || !String(v.id_card).trim()) {
        wx.showToast({ title: `请填写第${i + 1}位来访人员的身份证号`, icon: 'none' })
        return
      }
      if (!/^\d{17}[\dXx]$/.test(String(v.id_card).trim())) {
        wx.showToast({ title: `第${i + 1}位来访人员身份证号格式不正确`, icon: 'none' })
        return
      }
    }
    this.doSubmit(this.buildPayload(false))
  },

  saveDraft() {
    this.doSubmit(this.buildPayload(true))
  },

  doSubmit(payload) {
    const token = wx.getStorageSync('business_token')
    if (!token) {
      wx.showToast({ title: '请先登录', icon: 'none' })
      return
    }
    wx.showLoading({ title: '提交中' })
    wx.request({
      url: BASE_URL + '/api/work-orders',
      method: 'POST',
      header: {
        'content-type': 'application/json',
        'Authorization': 'Bearer ' + token
      },
      data: payload,
      success: (res) => {
        if (res.data.success) {
          wx.showToast({ title: res.data.message || '成功', icon: 'success' })
          setTimeout(() => wx.navigateBack(), 1200)
        } else {
          wx.showToast({ title: res.data.message || '提交失败', icon: 'none' })
        }
      },
      fail: () => wx.showToast({ title: '无法连接服务器', icon: 'none' }),
      complete: () => wx.hideLoading()
    })
  }
})

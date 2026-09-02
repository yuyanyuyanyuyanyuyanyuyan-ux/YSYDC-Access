const { BASE_URL } = require('../../config')

Page({
  data: {
    company: '',
    visitors: [],
    entry_date: '',
    entry_time: '',
    exit_date: '',
    exit_time: '',
    reasons: ['设备维护', '施工', '参观考察', '业务洽谈', '其他'],
    reason_index: -1,
    reason: '',
    area: '',
    contact_name: '',
    contact_phone: '',
    accompanying_person: ''
  },

  input(e) {
    const field = e.currentTarget.dataset.field
    this.setData({ [field]: e.detail.value })
  },

  onReasonChange(e) {
    const i = Number(e.detail.value)
    this.setData({ reason_index: i, reason: this.data.reasons[i] })
  },

  onDateChange(e) {
    const field = e.currentTarget.dataset.field
    this.setData({ [field]: e.detail.value })
  },

  onTimeChange(e) {
    const field = e.currentTarget.dataset.field
    this.setData({ [field]: e.detail.value })
  },

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

  submit() {
    const entry_time = this.data.entry_date + (this.data.entry_time ? ' ' + this.data.entry_time : '')
    const exit_time = this.data.exit_date + (this.data.exit_time ? ' ' + this.data.exit_time : '')
    const userId = wx.getStorageSync('user_id')
    if (!userId) {
      wx.showToast({ title: '请先登录', icon: 'none' })
      return
    }
    if (!this.data.company.trim()) {
      wx.showToast({ title: '请输入来访单位', icon: 'none' })
      return
    }
    wx.showLoading({ title: '提交中' })
    wx.request({
      url: BASE_URL + '/api/reservations',
      method: 'POST',
      header: { 'content-type': 'application/json' },
      data: {
        visitor_id: userId,
        company: this.data.company,
        visitors: this.data.visitors,
        entry_time,
        exit_time,
        reason: this.data.reason,
        area: this.data.area,
        contact_name: this.data.contact_name,
        contact_phone: this.data.contact_phone,
        accompanying_person: this.data.accompanying_person
      },
      success: (res) => {
        if (res.data.success) {
          wx.showToast({ title: '预约已提交', icon: 'success' })
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

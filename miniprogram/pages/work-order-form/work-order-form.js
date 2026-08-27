Page({
  data: {
    company: '',
    visit_time: '',
    visit_scale: '',
    contact_name: '',
    contact_phone: '',
    lead_person: ''
  },

  input(e) {
    const field = e.currentTarget.dataset.field
    this.setData({ [field]: e.detail.value })
  },

  submit() {
    const { company, visit_time, visit_scale, contact_name, contact_phone, lead_person } = this.data
    if (!company.trim()) {
      wx.showToast({ title: '请输入访客公司名称', icon: 'none' })
      return
    }
    const token = wx.getStorageSync('business_token')
    if (!token) {
      wx.showToast({ title: '请先登录', icon: 'none' })
      return
    }
    wx.showLoading({ title: '提交中' })
    wx.request({
      url: 'http://127.0.0.1:8000/api/work-orders',
      method: 'POST',
      header: {
        'content-type': 'application/json',
        'Authorization': 'Bearer ' + token
      },
      data: { company, visit_time, visit_scale, contact_name, contact_phone, lead_person },
      success: (res) => {
        if (res.data.success) {
          wx.showToast({ title: '工单已提交', icon: 'success' })
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

Page({
  data: {
    list: [],
    member: null
  },

  onShow() {
    const member = wx.getStorageSync('business_member')
    this.setData({ member })
    this.loadList()
  },

  loadList() {
    const token = wx.getStorageSync('business_token')
    if (!token) {
      wx.redirectTo({ url: '/pages/business-login/business-login' })
      return
    }
    wx.request({
      url: 'http://127.0.0.1:8000/api/work-orders/mine',
      method: 'GET',
      header: { 'Authorization': 'Bearer ' + token },
      success: (res) => {
        if (res.data.success) {
          this.setData({ list: res.data.list || [] })
        }
      },
      fail: () => wx.showToast({ title: '无法连接服务器', icon: 'none' })
    })
  },

  statusText(status) {
    if (status === 'approved') return '已通过'
    if (status === 'rejected') return '已驳回'
    return '待审批'
  },

  goCreate() {
    wx.navigateTo({ url: '/pages/work-order-form/work-order-form' })
  },

  logout() {
    wx.removeStorageSync('business_token')
    wx.removeStorageSync('business_member')
    wx.redirectTo({ url: '/pages/business-login/business-login' })
  }
})

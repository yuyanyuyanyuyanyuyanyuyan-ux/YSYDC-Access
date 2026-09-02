const { BASE_URL } = require('../../config')

Page({
  data: {
    tab: 0,
    orders: [],
    drafts: [],
    member: null
  },

  onShow() {
    this.setData({ member: wx.getStorageSync('business_member') })
    this.loadList()
  },

  switchTab(e) {
    this.setData({ tab: Number(e.currentTarget.dataset.tab) })
  },

  loadList() {
    const token = wx.getStorageSync('business_token')
    if (!token) {
      wx.redirectTo({ url: '/pages/business-login/business-login' })
      return
    }
    wx.request({
      url: BASE_URL + '/api/work-orders/mine',
      method: 'GET',
      header: { 'Authorization': 'Bearer ' + token },
      success: (res) => {
        if (res.data.success) {
          const all = res.data.list || []
          this.setData({
            orders: all.filter((w) => w.status !== 'draft'),
            drafts: all.filter((w) => w.status === 'draft')
          })
        }
      },
      fail: () => wx.showToast({ title: '无法连接服务器', icon: 'none' })
    })
  },

  statusText(status) {
    if (status === 'approved') return '已通过'
    if (status === 'rejected') return '已驳回'
    if (status === 'pending') return '审批中'
    return '草稿'
  },

  goCreate() {
    wx.navigateTo({ url: '/pages/work-order-form/work-order-form' })
  },

  goDetail(e) {
    wx.navigateTo({ url: '/pages/work-order-detail/work-order-detail?id=' + e.currentTarget.dataset.id })
  },

  logout() {
    wx.removeStorageSync('business_token')
    wx.removeStorageSync('business_member')
    wx.redirectTo({ url: '/pages/business-login/business-login' })
  }
})

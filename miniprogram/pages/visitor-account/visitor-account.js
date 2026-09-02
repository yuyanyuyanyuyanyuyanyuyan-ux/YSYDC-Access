const { BASE_URL } = require('../../config')

Page({
  data: {
    info: null
  },

  onShow() {
    const userId = wx.getStorageSync('user_id')
    if (!userId) {
      wx.reLaunch({ url: '/pages/visitor-login/visitor-login' })
      return
    }
    wx.request({
      url: `${BASE_URL}/api/visitor/info/${userId}`,
      method: 'GET',
      success: (res) => {
        if (res.data.success) {
          this.setData({ info: res.data.info })
        }
      },
      fail: () => wx.showToast({ title: '无法连接服务器', icon: 'none' })
    })
  },

  logout() {
    wx.removeStorageSync('user_id')
    wx.removeStorageSync('visitor')
    wx.removeStorageSync('work_order_id')
    wx.reLaunch({ url: '/pages/visitor-login/visitor-login' })
  }
})

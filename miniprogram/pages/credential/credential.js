Page({
  data: {
    credential: null
  },

  onLoad() {
    const userId = wx.getStorageSync('user_id')
    if (!userId) {
      wx.showToast({ title: '未获取到用户信息', icon: 'none' })
      return
    }
    wx.showLoading({ title: '加载凭证' })
    wx.request({
      url: `http://127.0.0.1:8000/api/credential/${userId}`,
      method: 'GET',
      success: (res) => {
        if (res.data.success) {
          this.setData({ credential: res.data.credential })
        } else {
          wx.showToast({ title: res.data.message || '暂无凭证', icon: 'none' })
        }
      },
      fail: () => wx.showToast({ title: '无法连接服务器', icon: 'none' }),
      complete: () => wx.hideLoading()
    })
  },

  goHome() {
    wx.switchTab({ url: '/pages/visitor-home/visitor-home' })
  }
})

Page({
  data: {
    workOrder: null
  },

  onLoad(options) {
    const token = wx.getStorageSync('business_token')
    wx.request({
      url: `http://127.0.0.1:8000/api/work-orders/${options.id}`,
      method: 'GET',
      header: { 'Authorization': 'Bearer ' + token },
      success: (res) => {
        if (res.data.success) {
          this.setData({ workOrder: res.data.work_order })
        } else {
          wx.showToast({ title: res.data.message || '加载失败', icon: 'none' })
        }
      },
      fail: () => wx.showToast({ title: '无法连接服务器', icon: 'none' })
    })
  }
})

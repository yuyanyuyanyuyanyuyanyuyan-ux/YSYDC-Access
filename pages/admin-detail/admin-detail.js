Page({
  data: {
    recordId: null,
    detail: {},
    history: [],
    currentTask: null
  },

  onLoad(options) {
    console.log('详情页接收到的参数：', options);
    // 防御：判断参数是否存在
    if (!options.recordId) {
      wx.showToast({ title: '参数缺失', icon: 'none' });
      return;
    }
    this.setData({ recordId: options.recordId });
    this.loadDetail();
  },

  loadDetail() {
    const recordId = this.data.recordId;
    wx.showLoading({ title: '加载中' });
    wx.request({
      url: `http://127.0.0.1:8000/api/approval-detail/${recordId}`,
      method: 'GET',
      success: (res) => {
        if (res.data.success) {
          this.setData({
            detail: res.data.detail,
            history: res.data.history,
            currentTask: res.data.current_task
          });
        } else {
          wx.showToast({ title: res.data.message || '加载失败', icon: 'none' });
        }
      },
      fail: () => {
        wx.showToast({ title: '无法连接服务器', icon: 'none' });
      },
      complete: () => wx.hideLoading()
    });
  }
});
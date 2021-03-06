// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef AnimatableValueKeyframe_h
#define AnimatableValueKeyframe_h

#include "core/CoreExport.h"
#include "core/animation/Keyframe.h"
#include "core/animation/animatable/AnimatableValue.h"

namespace blink {

class CORE_EXPORT AnimatableValueKeyframe : public Keyframe {
public:
    static PassRefPtrWillBeRawPtr<AnimatableValueKeyframe> create()
    {
        return adoptRefWillBeNoop(new AnimatableValueKeyframe);
    }
    void setPropertyValue(CSSPropertyID property, PassRefPtrWillBeRawPtr<AnimatableValue> value)
    {
        m_propertyValues.set(property, value);
    }
    void clearPropertyValue(CSSPropertyID property) { m_propertyValues.remove(property); }
    AnimatableValue* propertyValue(CSSPropertyID property) const
    {
        ASSERT(m_propertyValues.contains(property));
        return m_propertyValues.get(property);
    }
    PropertyHandleSet properties() const override;

    DECLARE_VIRTUAL_TRACE();

    class PropertySpecificKeyframe : public Keyframe::PropertySpecificKeyframe {
    public:
        PropertySpecificKeyframe(double offset, PassRefPtr<TimingFunction> easing, const AnimatableValue*, EffectModel::CompositeOperation);

        AnimatableValue* value() const { return m_value.get(); }
        const PassRefPtrWillBeRawPtr<AnimatableValue> getAnimatableValue() const final { return m_value; }

        PassOwnPtrWillBeRawPtr<Keyframe::PropertySpecificKeyframe> neutralKeyframe(double offset, PassRefPtr<TimingFunction> easing) const final;
        PassRefPtrWillBeRawPtr<Interpolation> maybeCreateInterpolation(PropertyHandle, Keyframe::PropertySpecificKeyframe& end, Element*, const ComputedStyle*) const final;

        DECLARE_VIRTUAL_TRACE();

    private:
        PropertySpecificKeyframe(double offset, PassRefPtr<TimingFunction> easing, PassRefPtrWillBeRawPtr<AnimatableValue>);

        PassOwnPtrWillBeRawPtr<Keyframe::PropertySpecificKeyframe> cloneWithOffset(double offset) const override;
        bool isAnimatableValuePropertySpecificKeyframe() const override { return true; }

        RefPtrWillBeMember<AnimatableValue> m_value;
    };

private:
    AnimatableValueKeyframe() { }

    AnimatableValueKeyframe(const AnimatableValueKeyframe& copyFrom);

    PassRefPtrWillBeRawPtr<Keyframe> clone() const override;
    PassOwnPtrWillBeRawPtr<Keyframe::PropertySpecificKeyframe> createPropertySpecificKeyframe(PropertyHandle) const override;

    bool isAnimatableValueKeyframe() const override { return true; }

    using PropertyValueMap = WillBeHeapHashMap<CSSPropertyID, RefPtrWillBeMember<AnimatableValue>>;
    PropertyValueMap m_propertyValues;
};

using AnimatableValuePropertySpecificKeyframe = AnimatableValueKeyframe::PropertySpecificKeyframe;

DEFINE_TYPE_CASTS(AnimatableValueKeyframe, Keyframe, value, value->isAnimatableValueKeyframe(), value.isAnimatableValueKeyframe());
DEFINE_TYPE_CASTS(AnimatableValuePropertySpecificKeyframe, Keyframe::PropertySpecificKeyframe, value, value->isAnimatableValuePropertySpecificKeyframe(), value.isAnimatableValuePropertySpecificKeyframe());

}

#endif
